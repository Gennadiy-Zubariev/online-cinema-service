class AccountsError(Exception):
    """Base class for accounts domain errors."""


class UserAlreadyExistsError(AccountsError):
    """Raised when a user with the given email already exists."""

    def __init__(self, email: str):
        self.email = email
        super().__init__(f"User with email {email} already exists")


class InvalidActivationTokenError(AccountsError):
    """Raised when the activation token does not exist."""


class ActivationTokenExpiredError(AccountsError):
    """Raised when the activation token has expired."""


class InvalidCredentialsError(AccountsError):
    """Raised when the email is unknown or the password is wrong."""


class UserNotActiveError(AccountsError):
    """Raised when credentials are valid but the account is not activated."""
