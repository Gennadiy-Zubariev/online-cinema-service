from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import RefreshToken
from src.accounts.security import (
    JWT_ALGORITHM,
    _create_jwt_token,
    create_access_token,
    create_refresh_token,
    hash_token,
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


async def stored_token_hashes(db_session: AsyncSession) -> list[str]:
    return list((await db_session.scalars(select(RefreshToken.token_hash))).all())


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


async def test_refresh_rotates_refresh_token(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    await create_user(is_active=True)
    old_token = await login(client)

    response = await client.post(REFRESH_URL)

    new_token = response.cookies["refresh_token"]
    assert new_token != old_token
    # Only the new token is stored: the old one is revoked.
    assert await stored_token_hashes(db_session) == [hash_token(new_token)]


async def test_refresh_cookie_has_same_attributes_as_login(
    client: AsyncClient, create_user: CreateUser
) -> None:
    # Different attributes (e.g. path) would make the browser keep two cookies.
    await create_user(is_active=True)
    await login(client)

    response = await client.post(REFRESH_URL)

    settings = get_settings()
    cookie_header = response.headers["set-cookie"].lower()
    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header
    assert "path=/api/v1/accounts" in cookie_header
    assert f"max-age={settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60}" in (
        cookie_header
    )
    assert ("secure" in cookie_header) is settings.COOKIE_SECURE


async def test_rotated_refresh_token_can_be_used_again(
    client: AsyncClient, create_user: CreateUser
) -> None:
    # The client's cookie jar takes the new cookie: refresh works repeatedly.
    await create_user(is_active=True)
    await login(client)

    first = await client.post(REFRESH_URL)
    second = await client.post(REFRESH_URL)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.cookies["refresh_token"] != first.cookies["refresh_token"]


async def test_reused_refresh_token_revokes_all_user_tokens(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    # A rotated token comes back = a stolen copy: every device must log in again.
    await create_user(is_active=True)
    other_device_token = await login(client)
    old_token = await login(client)
    rotated = await client.post(REFRESH_URL)
    new_token = rotated.cookies["refresh_token"]
    use_refresh_cookie(client, old_token)

    response = await client.post(REFRESH_URL)

    assert response.status_code == 401
    assert response.json() == INVALID_REFRESH_TOKEN
    assert await stored_token_hashes(db_session) == []
    for token in (new_token, other_device_token):
        use_refresh_cookie(client, token)
        assert (await client.post(REFRESH_URL)).status_code == 401


async def test_reused_refresh_token_keeps_other_users_tokens(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    other_user = await create_user(
        email="other@example.com", is_active=True, token_expires_in=None
    )
    other_token = create_refresh_token(other_user.id, get_settings())
    db_session.add(
        RefreshToken(
            user_id=other_user.id,
            token_hash=hash_token(other_token),
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    )
    await db_session.commit()
    await create_user(is_active=True)
    old_token = await login(client)
    await client.post(REFRESH_URL)
    use_refresh_cookie(client, old_token)

    response = await client.post(REFRESH_URL)

    assert response.status_code == 401
    assert await stored_token_hashes(db_session) == [hash_token(other_token)]


async def test_refresh_after_logout_revokes_other_devices(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    # After logout the browser has no cookie: a replay can only be a copy.
    await create_user(is_active=True)
    await login(client)
    other_device_token = client.cookies["refresh_token"]
    logged_out_token = await login(client)
    await client.post(LOGOUT_URL)
    use_refresh_cookie(client, logged_out_token)

    response = await client.post(REFRESH_URL)

    assert response.status_code == 401
    assert hash_token(other_device_token) not in await stored_token_hashes(db_session)


async def test_expired_refresh_token_does_not_revoke_user_tokens(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    # Rejected by decode, before the DB: no reuse detection, other tokens stay.
    user = await create_user(is_active=True)
    active_token = await login(client)
    use_refresh_cookie(
        client,
        _create_jwt_token(user.id, "refresh", timedelta(seconds=-1), get_settings()),
    )

    response = await client.post(REFRESH_URL)

    assert response.status_code == 401
    assert await stored_token_hashes(db_session) == [hash_token(active_token)]


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


async def test_refresh_rejects_deactivated_user(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    # Deactivation must stop refreshing, not only the current access token.
    user = await create_user(is_active=True, token_expires_in=None)
    await login(client)
    user.is_active = False
    await db_session.commit()

    response = await client.post(REFRESH_URL)

    assert response.status_code == 401
    assert response.json() == INVALID_REFRESH_TOKEN


async def test_refresh_of_deactivated_user_deletes_all_his_tokens(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    # Two devices; the user is deactivated directly in DB (no endpoint call).
    user = await create_user(is_active=True, token_expires_in=None)
    await login(client)
    await login(client)
    user.is_active = False
    await db_session.commit()

    await client.post(REFRESH_URL)
    # The real get_db() rolls back on close; the test override does not.
    # Without commit before raise the DELETE would be undone right here.
    await db_session.rollback()

    assert await stored_token_hashes(db_session) == []
