import hashlib
import secrets
from datetime import datetime, UTC, timedelta

import jwt
from pwdlib import PasswordHash

from src.accounts.exceptions import InvalidRefreshTokenError, InvalidAccessTokenError
from src.config.settings import Settings

JWT_ALGORITHM = "HS256"
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a password with Argon2.

    CPU-heavy: call via run_in_threadpool in async code.
    """
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Check a password against its Argon2 hash.

    CPU-heavy: call via run_in_threadpool in async code.
    """
    return password_hash.verify(password, hashed_password)


def generate_token() -> str:
    """Generate a random URL-safe token (activation, password reset, JWT jti)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of a token; only the hash is stored in the DB."""
    return hashlib.sha256(token.encode()).hexdigest()


def _create_jwt_token(
    user_id: int, token_type: str, expires_in: timedelta, settings: Settings
) -> str:
    """Encode a signed JWT with sub, type, iat, exp and a random jti.

    The jti keeps two tokens issued in the same second different
    (the stored refresh token hash is unique).
    """
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + expires_in,
        "jti": generate_token(),
    }
    return jwt.encode(
        payload, settings.SECRET_KEY.get_secret_value(), algorithm=JWT_ALGORITHM
    )


def create_access_token(user_id: int, settings: Settings) -> str:
    """Create a short-lived access JWT (ACCESS_TOKEN_EXPIRE_MINUTES)."""
    return _create_jwt_token(
        user_id,
        "access",
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        settings,
    )


def create_refresh_token(user_id: int, settings: Settings) -> str:
    """Create a refresh JWT (REFRESH_TOKEN_EXPIRE_DAYS).

    The caller stores its hash in the DB, so logout can revoke it.
    """
    return _create_jwt_token(
        user_id,
        "refresh",
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        settings,
    )


def _decode_jwt_token(token: str, token_type: str, settings: Settings) -> int:
    """Verify a JWT of the given type and return the user id from sub.

    Raises jwt.InvalidTokenError on a bad signature, expiry, missing claims
    or a different token type (a refresh token must not pass as access).
    """
    payload = jwt.decode(
        token,
        settings.SECRET_KEY.get_secret_value(),
        algorithms=[JWT_ALGORITHM],
        options={"require": ["exp", "iat", "sub", "type", "jti"]},
    )
    if payload["type"] != token_type:
        raise jwt.InvalidTokenError("Unexpected token type")
    return int(payload["sub"])


def decode_access_token(token: str, settings: Settings) -> int:
    """Return the user id from an access JWT.

    Raises InvalidAccessTokenError for any invalid token.
    """
    try:
        return _decode_jwt_token(token, "access", settings)
    except jwt.InvalidTokenError as error:
        raise InvalidAccessTokenError() from error


def decode_refresh_token(token: str, settings: Settings) -> int:
    """Return the user id from a refresh JWT.

    Raises InvalidRefreshTokenError for any invalid token.
    Does not check revocation: that needs the DB (see refresh_access_token).
    """
    try:
        return _decode_jwt_token(token, "refresh", settings)
    except jwt.InvalidTokenError as error:
        raise InvalidRefreshTokenError() from error
