"""API functions for refunds."""

import logging
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.db import transaction
from mitol.google_sheets.utils import ResultType
from mitol.google_sheets_refunds.utils import RefundRequestRow
from mitol.payment_gateway.api import PaymentGateway

from payments.models import Line, Order
from refunds.exceptions import (
    RefundOrderImproperStateError,
    RefundOrderPaymentTypeUnsupportedError,
    RefundRequestImproperStateError,
    RefundSheetPreflightFailedError,
    RefundTransactionFailedError,
)
from refunds.models import Request, RequestLine, RequestProcessingCode, RequestRecipient
from system_meta.models import Product
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
    requester: AbstractBaseUser,
    order: Order,
    *,
    lines: list[Line] | None = None,
    skip_event: bool = False,
) -> Request:
    """Create a refund request from an order."""

    if order.state != Order.STATE.FULFILLED:
        msg = "Order must be fulfilled to create a refund request."
        raise RefundOrderImproperStateError(msg)

    request = Request.objects.create(order=order, requester=requester)

    process_lines = lines if lines and len(lines) else order.lines.all()

    for line in process_lines:
        if line.order == order:
            RequestLine.objects.create(refund_request=request, line=line)

    if not skip_event:
        # If we're processing a refund from Google Sheets, we don't want to fire
        # these.
        pm.hook.refund_created(refund_id=request.pk)
    request.refresh_from_db()

    return request


@transaction.atomic
def process_approved_refund(request: Request) -> None:
    """
    Generate a CyberSource refund request for the approved lines in the refund request.
    """

    if request.status != REFUND_STATUS_APPROVED:
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

        order.state = Order.STATE.REFUNDED
        order.save()

        pm.hook.refund_issued(refund_id=request.id)

        return True

    refund_dict = {
        "transaction_id": transaction_dict["transaction_id"],
        "req_amount": str(refund_amount),
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
            transaction_id=response.transaction_id,
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

        order.state = Order.STATE.REFUNDED
        order.save()

        pm.hook.refund_issued(refund_id=request.id)

        return True

    msg = f"Refund request {request} failed to process: {response}"
    request.status = REFUND_STATUS_FAILED
    request.save()

    raise RefundTransactionFailedError(msg)


def _preflight_gsheet_request_row(row: RefundRequestRow) -> tuple[Order, Line]:
    """
    Run pre-flight check for the refund request.

    This includes making sure the product being refunded is on the order and
    that the total price of the line is not $0.00.
    """

    order = Order.objects.get(reference_number=row.order_ref_num)

    try:
        product = Product.all_objects.get(sku=row.product_id)
        line = order.lines.filter(product_version__object_id=str(product.id)).get()
    except Product.DoesNotExist:
        message = (
            f"Order {order.reference_number} does not contain a line "
            f"with SKU {row.product_id}"
        )
        log.exception(message)
        raise RefundSheetPreflightFailedError(message) from None

    if line.total_price == Decimal(0):
        message = (
            f"Order {order.reference_number} line {line} has a "
            "total price of $0.00; can't process"
        )
        log.error(message)
        raise RefundSheetPreflightFailedError(message)

    return (
        order,
        line,
    )


def process_gsheet_request_row(row: RefundRequestRow) -> tuple[ResultType, str | None]:
    """
    Process the refund request row that was seen in Google Sheets.

    If we've hit this, the row is ready to be refunded. The logic that filters
    out rows that aren't ready is in the ol-django google_sheets_refunds app.

    Args:
    - row (RefundRequestRow): The row to process.
    Returns:
    tuple of:
        - ResultType: The result of the processing.
        - str|None: An error message if the processing failed.
    """

    try:
        order, line = _preflight_gsheet_request_row(row)
    except RefundSheetPreflightFailedError as e:
        return ResultType.FAILED, str(e)

    log.debug("process_gsheet_request_row: processing order %s", order.reference_number)

    try:
        request = create_request_from_order(
            order.purchaser, order, skip_event=True, lines=[line]
        )
        request.save()
    except RefundOrderImproperStateError:
        log.exception(
            "Order %s must be in fulfilled state to process", order.reference_number
        )
        return ResultType.FAILED, "Order must be in fulfilled state to process."

    log.debug("process_gsheet_request_row: created request %s", request.pk)

    try:
        log.debug("process_gsheet_request_row: approving request %s", request.pk)
        request.approve("Approved via Google Sheets", skip_process_delay=True)
    except RefundRequestImproperStateError:
        log.exception("Request %s is in an improper state", request.pk)
        return ResultType.FAILED, "Request is in an improper state."
    except RefundOrderPaymentTypeUnsupportedError:
        log.exception(
            "Order %s for request %s is a PayPal order; can't process",
            order.reference_number,
            request.pk,
        )
        return (
            ResultType.FAILED,
            f"Order {order.reference_number} contains a PayPal payment; can't process.",
        )
    except RefundTransactionFailedError as e:
        log.exception("Request %s transaction failed to process: %s", request.pk, e.msg)
        return (
            ResultType.FAILED,
            f"Transaction failed to process: {e.msg}",
        )

    return (ResultType.PROCESSED, "Processed successfully")
