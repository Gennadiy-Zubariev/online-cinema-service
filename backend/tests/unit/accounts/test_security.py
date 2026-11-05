from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from pydantic import SecretStr

from src.accounts.exceptions import InvalidAccessTokenError, InvalidRefreshTokenError
from src.accounts.security import (
    JWT_ALGORITHM,
    _create_jwt_token,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)
from src.config.settings import Settings, get_settings


def test_hash_password_does_not_return_plain_password() -> None:
    assert hash_password("StrongPass1!") != "StrongPass1!"


def test_hash_password_uses_random_salt() -> None:
    assert hash_password("StrongPass1!") != hash_password("StrongPass1!")


def test_verify_password_accepts_correct_password() -> None:
    hashed = hash_password("StrongPass1!")

    assert verify_password("StrongPass1!", hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("StrongPass1!")

    assert verify_password("WrongPass1!", hashed) is False


def test_generate_token_returns_unique_tokens() -> None:
    assert generate_token() != generate_token()


def test_hash_token_is_deterministic() -> None:
    token = generate_token()

    assert hash_token(token) == hash_token(token)


def test_hash_token_returns_sha256_hex_digest() -> None:
    token_hash = hash_token(generate_token())

    assert len(token_hash) == 64
    assert all(char in "0123456789abcdef" for char in token_hash)


def decode(token: str) -> dict[str, Any]:
    settings = get_settings()
    payload: dict[str, Any] = jwt.decode(
        token, settings.SECRET_KEY.get_secret_value(), algorithms=[JWT_ALGORITHM]
    )
    return payload


def test_create_access_token_payload() -> None:
    settings = get_settings()

    payload = decode(create_access_token(5, settings))

    assert payload["sub"] == "5"
    assert payload["type"] == "access"
    assert payload["exp"] - payload["iat"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def test_create_refresh_token_payload() -> None:
    settings = get_settings()

    payload = decode(create_refresh_token(5, settings))

    assert payload["sub"] == "5"
    assert payload["type"] == "refresh"
    assert (
        payload["exp"] - payload["iat"]
        == settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )


def test_tokens_created_at_same_moment_are_unique() -> None:
    # Same user and second -> without `jti` the JWTs would be identical.
    settings = get_settings()

    assert create_refresh_token(5, settings) != create_refresh_token(5, settings)


def test_decode_refresh_token_returns_user_id() -> None:
    settings = get_settings()

    assert decode_refresh_token(create_refresh_token(5, settings), settings) == 5


def _token_without_jti() -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": "5",
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=1),
    }
    return jwt.encode(
        payload, settings.SECRET_KEY.get_secret_value(), algorithm=JWT_ALGORITHM
    )


@pytest.mark.parametrize(
    "make_token",
    [
        lambda s: create_access_token(5, s),
        lambda s: _create_jwt_token(5, "refresh", timedelta(seconds=-1), s),
        lambda s: create_refresh_token(5, s)[:-2] + "xx",
        lambda s: create_refresh_token(
            5, s.model_copy(update={"SECRET_KEY": SecretStr("x" * 64)})
        ),
        lambda s: _token_without_jti(),
        lambda s: "not-a-jwt",
    ],
    ids=["access_token", "expired", "tampered", "other_key", "no_jti", "garbage"],
)
def test_decode_refresh_token_rejects_invalid_token(
    make_token: Callable[[Settings], str],
) -> None:
    settings = get_settings()

    with pytest.raises(InvalidRefreshTokenError):
        decode_refresh_token(make_token(settings), settings)


def test_decode_access_token_returns_user_id() -> None:
    settings = get_settings()

    assert decode_access_token(create_access_token(5, settings), settings) == 5


@pytest.mark.parametrize(
    "make_token",
    [
        lambda s: create_refresh_token(5, s),
        lambda s: _create_jwt_token(5, "access", timedelta(seconds=-1), s),
        lambda s: create_access_token(5, s)[:-2] + "xx",
        lambda s: create_access_token(
            5, s.model_copy(update={"SECRET_KEY": SecretStr("x" * 64)})
        ),
        lambda s: "not-a-jwt",
    ],
    ids=["refresh_token", "expired", "tampered", "other_key", "garbage"],
)
def test_decode_access_token_rejects_invalid_token(
    make_token: Callable[[Settings], str],
) -> None:
    settings = get_settings()

    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(make_token(settings), settings)
