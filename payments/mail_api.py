from mitol.mail.api import get_message_sender
import logging

from payments.messages import SuccessfulOrderPaymentMessage

log = logging.getLogger(__name__)

def send_successful_order_payment_successful_email(
    order, email_subject, email_body
):
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
    except:  # noqa: E722
        log.exception("Error sending flexible price request status change email")