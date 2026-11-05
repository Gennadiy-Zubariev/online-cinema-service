from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import RefreshToken
from src.accounts.security import JWT_ALGORITHM, hash_token
from src.config.settings import get_settings
from tests.integration.accounts.conftest import USER_PASSWORD, CreateUser

LOGIN_URL = "/api/v1/accounts/login"
INVALID_CREDENTIALS = {"detail": "Invalid email or password."}


def decode(token: str) -> dict[str, object]:
    settings = get_settings()
    payload: dict[str, object] = jwt.decode(
        token, settings.SECRET_KEY.get_secret_value(), algorithms=[JWT_ALGORITHM]
    )
    return payload


async def login(
    client: AsyncClient, email: str = "user@example.com", password: str = USER_PASSWORD
) -> Response:
    return await client.post(LOGIN_URL, json={"email": email, "password": password})


async def test_login_returns_access_token(
    client: AsyncClient, create_user: CreateUser
) -> None:
    user = await create_user(is_active=True)

    response = await login(client)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    payload = decode(body["access_token"])
    assert payload["sub"] == str(user.id)
    assert payload["type"] == "access"


async def test_login_sets_refresh_token_cookie(
    client: AsyncClient, create_user: CreateUser
) -> None:
    await create_user(is_active=True)

    response = await login(client)

    refresh_token = response.cookies["refresh_token"]
    assert decode(refresh_token)["type"] == "refresh"
    assert "refresh_token" not in response.json()

    settings = get_settings()
    cookie_header = response.headers["set-cookie"].lower()
    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header
    assert "path=/api/v1/accounts" in cookie_header
    assert f"max-age={settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60}" in (
        cookie_header
    )
    assert ("secure" in cookie_header) is settings.COOKIE_SECURE


async def test_login_saves_hashed_refresh_token(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    user = await create_user(is_active=True)

    response = await login(client)

    token = await db_session.scalar(
        select(RefreshToken).where(RefreshToken.user_id == user.id)
    )
    assert token is not None
    assert token.token_hash == hash_token(response.cookies["refresh_token"])

    expected_expires_at = datetime.now(UTC) + timedelta(
        days=get_settings().REFRESH_TOKEN_EXPIRE_DAYS
    )
    assert abs(token.expires_at - expected_expires_at) < timedelta(minutes=1)


async def test_login_twice_keeps_both_refresh_tokens(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    # Each login is a separate session (device); `jti` keeps the JWTs unique.
    user = await create_user(is_active=True)

    first = await login(client)
    second = await login(client)

    assert first.cookies["refresh_token"] != second.cookies["refresh_token"]
    tokens = (
        await db_session.scalars(
            select(RefreshToken).where(RefreshToken.user_id == user.id)
        )
    ).all()
    assert len(tokens) == 2


async def test_login_is_case_insensitive_for_email(
    client: AsyncClient, create_user: CreateUser
) -> None:
    await create_user(email="user@example.com", is_active=True)

    response = await login(client, email="USER@Example.com")

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("email", "password"),
    [("user@example.com", "WrongPass1!"), ("nobody@example.com", USER_PASSWORD)],
    ids=["wrong_password", "unknown_email"],
)
async def test_login_rejects_invalid_credentials(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user: CreateUser,
    email: str,
    password: str,
) -> None:
    await create_user(is_active=True)

    response = await login(client, email=email, password=password)

    assert response.status_code == 401
    assert response.json() == INVALID_CREDENTIALS
    assert response.headers["www-authenticate"] == "Bearer"
    assert "refresh_token" not in response.cookies
    assert await db_session.scalar(select(RefreshToken)) is None


async def test_login_rejects_inactive_user(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    await create_user(is_active=False)

    response = await login(client)

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Account is not activated. Please check your email."
    }
    assert await db_session.scalar(select(RefreshToken)) is None


async def test_login_inactive_user_with_wrong_password_gets_401(
    client: AsyncClient, create_user: CreateUser
) -> None:
    # Password is checked first: 403 must not reveal that the email exists.
    await create_user(is_active=False)

    response = await login(client, password="WrongPass1!")

    assert response.status_code == 401
    assert response.json() == INVALID_CREDENTIALS


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "user@example.com"},
        {"email": "not-an-email", "password": USER_PASSWORD},
        {"email": "user@example.com", "password": ""},
        {"email": "user@example.com", "password": "x" * 129},
    ],
    ids=["missing_password", "invalid_email", "empty_password", "too_long_password"],
)
async def test_login_rejects_invalid_payload(
    client: AsyncClient, payload: dict[str, str]
) -> None:
    response = await client.post(LOGIN_URL, json=payload)

    assert response.status_code == 422
