class OrderError(Exception):
    """Base class for order domain errors."""


class EmptyCartError(OrderError):
    """Raised when no cart items in cart"""

    def __init__(self) -> None:
        super().__init__("Cart is empty.")


class AllMoviesPurchasedError(OrderError):
    """Raised when all cart elements purchased"""

    def __init__(self) -> None:
        super().__init__("All movies in the cart are already purchased.")
