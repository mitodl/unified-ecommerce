"""Message templates for payments."""

from mitol.mail.messages import TemplatedMessage


class SuccessfulOrderPaymentMessage(TemplatedMessage):
    """Template for the successful order message"""

    template_name = "mail/order_payment"
    name = "Successful Order Payment"
