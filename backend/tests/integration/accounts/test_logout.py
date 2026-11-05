from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import RefreshToken
from src.accounts.security import hash_token
from tests.integration.accounts.conftest import USER_PASSWORD, CreateUser

LOGIN_URL = "/api/v1/accounts/login"
LOGOUT_URL = "/api/v1/accounts/logout"


async def login(client: AsyncClient) -> str:
    """Log in; the client's cookie jar keeps the refresh cookie. Returns it."""
    response = await client.post(
        LOGIN_URL, json={"email": "user@example.com", "password": USER_PASSWORD}
    )
    assert response.status_code == 200
    return response.cookies["refresh_token"]


async def refresh_token_hashes(db_session: AsyncSession) -> list[str]:
    return list((await db_session.scalars(select(RefreshToken.token_hash))).all())


async def test_logout_deletes_refresh_token(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    await create_user(is_active=True)
    await login(client)

    response = await client.post(LOGOUT_URL)

    assert response.status_code == 204
    assert response.content == b""
    assert await refresh_token_hashes(db_session) == []


async def test_logout_clears_refresh_cookie(
    client: AsyncClient, create_user: CreateUser
) -> None:
    await create_user(is_active=True)
    await login(client)

    response = await client.post(LOGOUT_URL)

    # Same path/attributes as on login, otherwise the browser keeps the cookie.
    cookie_header = response.headers["set-cookie"].lower()
    assert cookie_header.startswith("refresh_token=")
    assert "max-age=0" in cookie_header
    assert "path=/api/v1/accounts" in cookie_header
    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header
    assert "refresh_token" not in client.cookies


async def test_logout_keeps_other_sessions(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    await create_user(is_active=True)
    other_device_token = await login(client)
    await login(client)  # the jar now holds this device's token

    await client.post(LOGOUT_URL)

    assert await refresh_token_hashes(db_session) == [hash_token(other_device_token)]


async def test_logout_without_cookie_returns_204(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    await create_user(is_active=True)
    token = await login(client)
    client.cookies.clear()

    response = await client.post(LOGOUT_URL)

    assert response.status_code == 204
    assert await refresh_token_hashes(db_session) == [hash_token(token)]


async def test_logout_with_unknown_token_returns_204(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    await create_user(is_active=True)
    token = await login(client)
    client.cookies.clear()
    client.cookies.set("refresh_token", "unknown-token")

    response = await client.post(LOGOUT_URL)

    assert response.status_code == 204
    assert await refresh_token_hashes(db_session) == [hash_token(token)]


async def test_logout_is_idempotent(
    client: AsyncClient, create_user: CreateUser
) -> None:
    await create_user(is_active=True)
    await login(client)

    first = await client.post(LOGOUT_URL)
    second = await client.post(LOGOUT_URL)

    assert first.status_code == 204
    assert second.status_code == 204
