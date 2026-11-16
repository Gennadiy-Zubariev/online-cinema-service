class PaymentError(Exception):
    """Base class for payment domain errors."""


class InvalidWebhookError(PaymentError):
    """Raised when a webhook payload or its signature is invalid."""

    def __init__(self) -> None:
        super().__init__("Invalid webhook signature.")
