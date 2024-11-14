"""Mail functions for payments."""

import logging
from email.utils import formataddr

from django.contrib.auth import get_user_model
from mitol.mail.api import get_message_sender

from payments.messages import SuccessfulOrderPaymentMessage

log = logging.getLogger(__name__)
User = get_user_model()


def send_successful_order_payment_email(order, email_subject, email_body):
    """Send order payment email on successful transaction"""

    try:
        with get_message_sender(SuccessfulOrderPaymentMessage) as sender:
            sender.build_and_send_message(
                order.purchaser.email,
                {
                    "subject": email_subject,
                    "first_name": order.purchaser.first_name,
                    "message": email_body,
                },
            )
        log.info("Sent successful order payment email to %s", order.purchaser.email)
    except:  # noqa: E722
        log.exception("Error sending successful order payment email")


def format_recipient(user: User) -> str:
    """Format the user as a recipient"""

    return formataddr((user.name, user.email))
