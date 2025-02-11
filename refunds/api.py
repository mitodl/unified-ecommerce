"""API functions for refunds."""

import logging
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser

from payments.models import Line, Order
from refunds.models import Request, RequestLine, RequestProcessingCode, RequestRecipient
from unified_ecommerce.celery import app
from unified_ecommerce.plugin_manager import get_plugin_manager

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

    return request
