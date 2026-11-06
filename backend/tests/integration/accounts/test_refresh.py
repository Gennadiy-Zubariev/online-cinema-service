from datetime import timedelta

import jwt
import pytest
from httpx import AsyncClient

from src.accounts.security import (
    JWT_ALGORITHM,
    _create_jwt_token,
    create_access_token,
    create_refresh_token,
)
from src.config.settings import get_settings
from tests.integration.conftest import USER_PASSWORD, CreateUser

LOGIN_URL = "/api/v1/accounts/login"
LOGOUT_URL = "/api/v1/accounts/logout"
REFRESH_URL = "/api/v1/accounts/refresh"
INVALID_REFRESH_TOKEN = {
    "detail": "Invalid or expired refresh token. Please log in again."
}


async def login(client: AsyncClient) -> str:
    """Log in; the client's cookie jar keeps the refresh cookie. Returns it."""
    response = await client.post(
        LOGIN_URL, json={"email": "user@example.com", "password": USER_PASSWORD}
    )
    assert response.status_code == 200
    return response.cookies["refresh_token"]


def use_refresh_cookie(client: AsyncClient, token: str) -> None:
    client.cookies.clear()
    client.cookies.set("refresh_token", token)


async def test_refresh_returns_new_access_token(
    client: AsyncClient, create_user: CreateUser
) -> None:
    user = await create_user(is_active=True)
    await login(client)

    response = await client.post(REFRESH_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    settings = get_settings()
    payload = jwt.decode(
        body["access_token"],
        settings.SECRET_KEY.get_secret_value(),
        algorithms=[JWT_ALGORITHM],
    )
    assert payload["sub"] == str(user.id)
    assert payload["type"] == "access"


def test_access_token_ttl_is_shorter_than_refresh_token_ttl() -> None:
    # ТЗ: refresh gives a new access token with a shorter TTL.
    settings = get_settings()

    assert timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES) < timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )


async def test_refresh_does_not_change_refresh_cookie(
    client: AsyncClient, create_user: CreateUser
) -> None:
    await create_user(is_active=True)
    refresh_token = await login(client)

    response = await client.post(REFRESH_URL)

    assert "set-cookie" not in response.headers
    assert client.cookies["refresh_token"] == refresh_token


async def test_refresh_without_cookie_returns_401(client: AsyncClient) -> None:
    response = await client.post(REFRESH_URL)

    assert response.status_code == 401
    assert response.json() == INVALID_REFRESH_TOKEN
    assert response.headers["www-authenticate"] == "Bearer"


async def test_refresh_after_logout_returns_401(
    client: AsyncClient, create_user: CreateUser
) -> None:
    # The JWT itself is still valid; only the DB knows it was revoked.
    await create_user(is_active=True)
    refresh_token = await login(client)
    await client.post(LOGOUT_URL)
    use_refresh_cookie(client, refresh_token)

    response = await client.post(REFRESH_URL)

    assert response.status_code == 401
    assert response.json() == INVALID_REFRESH_TOKEN


async def test_refresh_rejects_valid_jwt_not_saved_in_db(
    client: AsyncClient, create_user: CreateUser
) -> None:
    user = await create_user(is_active=True)
    use_refresh_cookie(client, create_refresh_token(user.id, get_settings()))

    response = await client.post(REFRESH_URL)

    assert response.status_code == 401


@pytest.mark.parametrize("token_kind", ["access", "expired", "garbage"])
async def test_refresh_rejects_invalid_token(
    client: AsyncClient, create_user: CreateUser, token_kind: str
) -> None:
    user = await create_user(is_active=True)
    settings = get_settings()
    tokens = {
        "access": create_access_token(user.id, settings),
        "expired": _create_jwt_token(
            user.id, "refresh", timedelta(seconds=-1), settings
        ),
        "garbage": "not-a-jwt",
    }
    use_refresh_cookie(client, tokens[token_kind])

    response = await client.post(REFRESH_URL)

    assert response.status_code == 401
    assert response.json() == INVALID_REFRESH_TOKEN
