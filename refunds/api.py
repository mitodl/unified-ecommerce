"""API functions for refunds."""

import logging
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser

from payments.models import Line, Order
from refunds.models import Request, RequestLine, RequestProcessingCode, RequestRecipient

log = logging.getLogger(__name__)
User = get_user_model()


def send_request_access_code_email(code: RequestProcessingCode) -> None:
    """Send an email to the recipient with the access code."""

    log.info("Sending refund request access code email to %s", code.email)


def create_request_access_codes(request: Request) -> None:
    """
    Create access codes for the request.

    A batch of these get sent out to the processing recipients when the request
    is created. The batch IDs need to be created when these are sent out - they
    don't get stored anywhere but with the actual code.
    """

    recipients = RequestRecipient.objects.filter(
        system=request.order.integrated_system
    ).all()
    batch_uuid = uuid4()

    for recipient in recipients:
        # Create the access code
        access_code = RequestProcessingCode.objects.create(
            request=request,
            email=recipient.email,
            batch_uuid=batch_uuid,
            system=request.order.integrated_system,
        )
        access_code.send_email()


def create_request_from_order(
    requester: AbstractBaseUser, order: Order, *, lines: list[Line] = []
) -> Request:
    """Create a refund request from an order."""

    if order.state != Order.STATE.FULFILLED:
        raise ValueError("Order must be fulfilled to create a refund request.")

    request = Request.objects.create(order=order, requester=requester)

    process_lines = lines if lines else order.lines.all()

    for line in process_lines:
        RequestLine.objects.create(request=request, line=line) if line.order == order else None

    return request
