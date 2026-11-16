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


class OrderNotFoundError(OrderError):
    """Raised when the order does not exist or belongs to another user."""

    def __init__(self) -> None:
        super().__init__("Order not found.")


class OrderNotPendingError(OrderError):
    """Raised when paying for an order that is not pending."""

    def __init__(self) -> None:
        super().__init__("Only pending orders can be paid.")


class OrderMoviesPurchasedError(OrderError):
    """Raised when all movies of the order are already purchased."""

    def __init__(self) -> None:
        super().__init__(
            "All movies in the order are already purchased. The order is canceled."
        )
