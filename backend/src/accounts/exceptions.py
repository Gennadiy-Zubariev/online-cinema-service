class AccountsError(Exception):
    """Base class for accounts domain errors."""


class UserAlreadyExistsError(AccountsError):
    """Raised when a user with the given email already exists."""
