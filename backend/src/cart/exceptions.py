class CartError(Exception):
    """Base class for cart domain errors."""


class MovieAlreadyPurchasedError(CartError):
    """Raised when adding a movie the user has already purchased."""

    def __init__(self) -> None:
        super().__init__("Movie already purchased")
