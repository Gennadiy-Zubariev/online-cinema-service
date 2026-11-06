from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.security import (
    _create_jwt_token,
    create_access_token,
    create_refresh_token,
)
from src.config.settings import get_settings
from tests.integration.conftest import USER_PASSWORD, CreateUser

LOGIN_URL = "/api/v1/accounts/login"
CHANGE_PASSWORD_URL = "/api/v1/accounts/change-password"
NEW_PASSWORD = "NewStrongPass2@"
INVALID_ACCESS_TOKEN = {"detail": "Invalid or expired access token."}


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def login(client: AsyncClient, password: str = USER_PASSWORD) -> int:
    response = await client.post(
        LOGIN_URL, json={"email": "user@example.com", "password": password}
    )
    return response.status_code


async def access_token_for(client: AsyncClient) -> str:
    response = await client.post(
        LOGIN_URL, json={"email": "user@example.com", "password": USER_PASSWORD}
    )
    token: str = response.json()["access_token"]
    return token


async def test_change_password_replaces_password(
    client: AsyncClient, create_user: CreateUser
) -> None:
    await create_user(is_active=True)
    token = await access_token_for(client)

    response = await client.post(
        CHANGE_PASSWORD_URL,
        json={"old_password": USER_PASSWORD, "new_password": NEW_PASSWORD},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Password changed successfully."}
    assert await login(client, USER_PASSWORD) == 401
    assert await login(client, NEW_PASSWORD) == 200


async def test_change_password_rejects_wrong_old_password(
    client: AsyncClient, create_user: CreateUser
) -> None:
    await create_user(is_active=True)
    token = await access_token_for(client)

    response = await client.post(
        CHANGE_PASSWORD_URL,
        json={"old_password": "WrongPass1!", "new_password": NEW_PASSWORD},
        headers=auth_header(token),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Old password is incorrect."}
    assert await login(client, USER_PASSWORD) == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"old_password": USER_PASSWORD, "new_password": "weakpass1!"},
        {"old_password": USER_PASSWORD, "new_password": "Sh0rt!"},
        {"old_password": "", "new_password": NEW_PASSWORD},
        {"old_password": "x" * 129, "new_password": NEW_PASSWORD},
        {"old_password": USER_PASSWORD},
    ],
    ids=[
        "weak_new_password",
        "short_new_password",
        "empty_old_password",
        "too_long_old_password",
        "missing_new_password",
    ],
)
async def test_change_password_rejects_invalid_payload(
    client: AsyncClient, create_user: CreateUser, payload: dict[str, str]
) -> None:
    await create_user(is_active=True)
    token = await access_token_for(client)

    response = await client.post(
        CHANGE_PASSWORD_URL, json=payload, headers=auth_header(token)
    )

    assert response.status_code == 422
    assert await login(client, USER_PASSWORD) == 200


# --- get_current_user: checked through its first consumer ---

PAYLOAD = {"old_password": USER_PASSWORD, "new_password": NEW_PASSWORD}


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer"}],
    ids=["no_header", "wrong_scheme", "empty_token"],
)
async def test_change_password_requires_bearer_token(
    client: AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.post(CHANGE_PASSWORD_URL, json=PAYLOAD, headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("token_kind", ["refresh", "expired", "garbage"])
async def test_change_password_rejects_invalid_access_token(
    client: AsyncClient, create_user: CreateUser, token_kind: str
) -> None:
    user = await create_user(is_active=True)
    settings = get_settings()
    tokens = {
        "refresh": create_refresh_token(user.id, settings),
        "expired": _create_jwt_token(
            user.id, "access", timedelta(seconds=-1), settings
        ),
        "garbage": "not-a-jwt",
    }

    response = await client.post(
        CHANGE_PASSWORD_URL, json=PAYLOAD, headers=auth_header(tokens[token_kind])
    )

    assert response.status_code == 401
    assert response.json() == INVALID_ACCESS_TOKEN
    assert response.headers["www-authenticate"] == "Bearer"


async def test_change_password_rejects_token_of_deleted_user(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    # A valid JWT is not enough: the user must still exist in the DB.
    user = await create_user(is_active=True)
    token = create_access_token(user.id, get_settings())
    await db_session.delete(user)
    await db_session.commit()

    response = await client.post(
        CHANGE_PASSWORD_URL, json=PAYLOAD, headers=auth_header(token)
    )

    assert response.status_code == 401
    assert response.json() == INVALID_ACCESS_TOKEN
