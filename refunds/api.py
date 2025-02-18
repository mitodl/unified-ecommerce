"""API functions for refunds."""

import logging
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.db import transaction
from mitol.payment_gateway.api import PaymentGateway

from payments.models import Line, Order
from refunds.exceptions import (
    RefundOrderPaymentTypeUnsupportedError,
    RefundRequestImproperStateError,
    RefundTransactionFailedError,
)
from refunds.models import Request, RequestLine, RequestProcessingCode, RequestRecipient
from unified_ecommerce.celery import app
from unified_ecommerce.constants import (
    CYBERSOURCE_REFUND_SUCCESS_STATES,
    REFUND_STATUS_APPROVED,
    REFUND_STATUS_APPROVED_COMPLETE,
    REFUND_STATUS_FAILED,
    TRANSACTION_TYPE_PAYMENT,
    TRANSACTION_TYPE_REFUND,
)
from unified_ecommerce.plugin_manager import get_plugin_manager
from unified_ecommerce.utils import now_in_utc

pm = get_plugin_manager()
log = logging.getLogger(__name__)
User = get_user_model()


@app.task
def send_request_access_code_email(code_id: int) -> None:
    """Send an email to the recipient with the access code."""

    code = RequestProcessingCode.objects.get(pk=code_id)
    log.info("Sending refund request access code email to %s", code.email)


def create_request_access_codes(request: Request) -> None:
    """
    Create access codes for the request.

    A batch of these get sent out to the processing recipients when the request
    is created. The batch IDs need to be created when these are sent out - they
    don't get stored anywhere but with the actual code.
    """

    log.debug("Generating request access codes for request %s", request.pk)

    recipients = RequestRecipient.objects.filter(
        integrated_system=request.order.integrated_system
    ).all()
    batch_uuid = uuid4()

    log.debug("Access code batch %s", batch_uuid)
    log.debug("%s recipients", len(recipients))

    for recipient in recipients:
        # Create the access code
        access_code = RequestProcessingCode.objects.create(
            refund_request=request,
            email=recipient.email,
            code_batch=batch_uuid,
        )
        access_code.save()
        log.debug("Sending access code %s", access_code.approve_code)
        send_request_access_code_email.delay(access_code.pk)


def create_request_from_order(
    requester: AbstractBaseUser, order: Order, *, lines: list[Line] | None = None
) -> Request:
    """Create a refund request from an order."""

    if order.state != Order.STATE.FULFILLED:
        msg = "Order must be fulfilled to create a refund request."
        raise ValueError(msg)

    request = Request.objects.create(order=order, requester=requester)

    process_lines = lines if lines and len(lines) else order.lines.all()

    for line in process_lines:
        if line.order == order:
            RequestLine.objects.create(refund_request=request, line=line)

    pm.hook.refund_created(refund_id=request.pk)
    request.refresh_from_db()

    return request


@transaction.atomic
def process_approved_refund(request: Request, *, auto_approved: bool = False) -> None:
    """
    Generate a CyberSource refund request for the approved lines in the refund request.
    """

    if request.status != REFUND_STATUS_APPROVED and not auto_approved:
        msg = f"Request {request} must be approved to process."
        raise RefundRequestImproperStateError(msg)

    order = request.order
    order_recent_transaction = (
        order.transactions.filter(transaction_type=TRANSACTION_TYPE_PAYMENT)
        .order_by("-created_on")
        .first()
    )

    if not order_recent_transaction:
        message = f"No payment transactions exist for order_id {order.id}"
        log.error(message)
        return False, message

    transaction_dict = order_recent_transaction.data

    # Check for a PayPal payment - if there's one, we can't process it
    if "paypal_token" in transaction_dict:
        msg = (
            f"PayPal: Order {order.reference_number} contains a PayPal "
            "transaction. Please contact Finance to refund this order."
        )

        raise RefundOrderPaymentTypeUnsupportedError(msg)

    # Refund requests for CyberSource are much simpler than the payment request.
    # We just need to send the transaction ID, amount, and currency.

    refund_amount = sum(line.refunded_amount for line in request.lines.all())

    if refund_amount == Decimal(0):
        # If we didn't refund anything, add a few bits of metadata and fire the
        # issued hooks.
        request.processed_date = now_in_utc()
        request.status = REFUND_STATUS_APPROVED_COMPLETE
        request.save()

        for line in request.lines.all():
            line.status = REFUND_STATUS_APPROVED_COMPLETE
            line.save()

        pm.hook.refund_issued(refund_id=request.id)

        return True

    refund_dict = {
        "transaction_id": transaction_dict["transaction_id"],
        "req_amount": refund_amount,
        "req_currency": transaction_dict["req_currency"],
    }

    log.debug("Refund request %s payload for CyberSource: %s", request, refund_dict)

    refund_gateway_request = PaymentGateway.create_refund_request(
        settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, refund_dict
    )

    response = PaymentGateway.start_refund(
        settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY,
        refund_gateway_request,
    )

    if response.state in CYBERSOURCE_REFUND_SUCCESS_STATES:
        # Save the transaction and update the underlying request and order.
        log.info("Refund request %s successfully processed", request)

        transaction = order.transactions.create(
            transaction_type=TRANSACTION_TYPE_REFUND,
            data=response.response_data,
            reason=request.refund_reason,
            amount=response.response_data.get("refundAmountDetails", {}).get(
                "refundAmount"
            ),
        )

        request.processed_date = transaction.created_on
        request.status = REFUND_STATUS_APPROVED_COMPLETE
        request.save()

        for line in request.lines.all():
            line.status = REFUND_STATUS_APPROVED_COMPLETE
            line.transactions.add(transaction)
            line.save()

        pm.hook.refund_issued(refund_id=request.id)

        return True

    msg = f"Refund request {request} failed to process: {response}"
    request.status = REFUND_STATUS_FAILED
    request.save()

    raise RefundTransactionFailedError(msg)
