"""Mail functions for refunds."""

import logging
from email.utils import formataddr

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser

from refunds.models import Request

log = logging.getLogger(__name__)
User = get_user_model()


def send_refund_created_email(refund_request_id: int):
    """Send refund created email"""

    refund_request = Request.objects.get(pk=refund_request_id)

    log.debug(
        "Sending refund created email to %s", refund_request.order.purchaser.email
    )


def send_refund_issued_email(refund_request_id: int):
    """Send refund issued email"""

    refund_request = Request.objects.get(pk=refund_request_id)

    log.debug("Sending refund issued email to %s", refund_request.order.purchaser.email)


def send_refund_denied_email(refund_request_id: int):
    """Send refund denied email"""

    refund_request = Request.objects.get(pk=refund_request_id)

    log.debug("Sending refund denied email to %s", refund_request.order.purchaser.email)


def format_recipient(user: AbstractBaseUser) -> str:
    """Format the user as a recipient"""

    return formataddr((user.name, user.email))
