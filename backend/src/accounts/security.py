import hashlib
import secrets
from datetime import datetime, UTC, timedelta

import jwt
from pwdlib import PasswordHash

from src.accounts.exceptions import InvalidRefreshTokenError
from src.config.settings import Settings

JWT_ALGORITHM = "HS256"
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _create_jwt_token(
    user_id: int, token_type: str, expires_in: timedelta, settings: Settings
) -> str:
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
    return _create_jwt_token(
        user_id,
        "access",
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        settings,
    )


def create_refresh_token(user_id: int, settings: Settings) -> str:
    return _create_jwt_token(
        user_id,
        "refresh",
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        settings,
    )


def decode_refresh_token(token: str, settings: Settings) -> int:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "iat", "sub", "type", "jti"]},
        )
    except jwt.InvalidTokenError as error:
        raise InvalidRefreshTokenError() from error

    if payload["type"] != "refresh":
        raise InvalidRefreshTokenError()
    return int(payload["sub"])
