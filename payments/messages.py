from mitol.mail.messages import TemplatedMessage


class SuccessfulOrderPaymentMessage(TemplatedMessage):
    template_name = "mail/order_payment"
    name = "Successful Order Payment"
