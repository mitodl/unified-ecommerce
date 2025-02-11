"""Custom exceptions for refunds."""

class RefundAlreadyCompleteError(Exception):
    """Raised when a refund has already been completed."""

    def __init__(self, *args: object) -> None:
        """Initialize the exception."""

        super().__init__(*args)
