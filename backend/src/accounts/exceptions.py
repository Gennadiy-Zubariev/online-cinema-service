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


class InvalidRefreshTokenError(AccountsError):
    """Raised when the refresh token is missing, invalid, expired or revoked."""


class InvalidAccessTokenError(AccountsError):
    """Raised when the access token is malformed, tampered with or expired."""


class IncorrectPasswordError(AccountsError):
    """Raised when the current (old) password does not match."""


class InvalidPasswordResetTokenError(AccountsError):
    """Raised when the password reset token is unknown, used or expired."""


class PermissionDeniedError(AccountsError):
    """Raised when the user's group is not allowed to perform the action."""


class UserNotFoundError(AccountsError):
    """Raised when no user exists with the given id."""


class UnsupportedAvatarTypeError(AccountsError):
    """Raised when the avatar is not a JPEG, PNG or WebP image."""


class AvatarTooLargeError(AccountsError):
    """Raised when the avatar exceeds the maximum allowed size."""
