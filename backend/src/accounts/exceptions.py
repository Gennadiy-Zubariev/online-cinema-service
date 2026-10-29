class AccountsError(Exception):
    """Base class for accounts domain errors."""


class UserAlreadyExistsError(AccountsError):
    """Raised when a user with the given email already exists."""

    def __init__(self, email: str):
        self.email = email
        super().__init__(f"User with email {email} already exists")
