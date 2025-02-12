"""Custom exceptions for refunds."""


class RefundAlreadyCompleteError(Exception):
    """Raised when a refund has already been completed."""

    def __init__(self, *args: object) -> None:
        """Initialize the exception."""

        super().__init__(*args)


class RefundOrderImproperStateError(Exception):
    """Raised when an order is in an improper state for refunding."""

    def __init__(self, *args: object) -> None:
        """Initialize the exception."""

        super().__init__(*args)


class RefundRequestImproperStateError(Exception):
    """Raised when a refund request is in an improper state for processing."""

    def __init__(self, *args: object) -> None:
        """Initialize the exception."""

        super().__init__(*args)


class RefundOrderPaymentTypeUnsupportedError(Exception):
    """
    Raised when an order has an unsupported payment type for refunding (e.g. PayPal).
    """

    def __init__(self, *args: object) -> None:
        """Initialize the exception."""

        super().__init__(*args)


class RefundTransactionFailedError(Exception):
    """Raised when a refund transaction fails."""

    def __init__(self, *args: object) -> None:
        """Initialize the exception."""

        super().__init__(*args)
