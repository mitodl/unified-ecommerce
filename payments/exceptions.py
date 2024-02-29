"""Exceptions for payments app."""


class PaypalRefundError(Exception):
    """Raised when attempting to refund an order that was paid via PayPal."""


class PaymentGatewayError(Exception):
    """
    Raised when the payment gateway gives us an error, but didn't raise its own
    exception.
    """
