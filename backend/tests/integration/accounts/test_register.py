from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import ActivationToken, User, UserGroup, UserGroupEnum
from src.config.settings import get_settings

REGISTER_URL = "/api/v1/accounts/register"
VALID_PASSWORD = "StrongPass1!"


async def test_register_returns_created_inactive_user(client: AsyncClient) -> None:
    response = await client.post(
        REGISTER_URL, json={"email": "user@example.com", "password": VALID_PASSWORD}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "user@example.com"
    assert body["is_active"] is False
    assert "password" not in body
    assert "hashed_password" not in body


async def test_register_lowercases_email(client: AsyncClient) -> None:
    response = await client.post(
        REGISTER_URL, json={"email": "User@Example.COM", "password": VALID_PASSWORD}
    )

    assert response.status_code == 201
    assert response.json()["email"] == "user@example.com"


async def test_register_saves_hashed_password_and_user_group(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post(
        REGISTER_URL, json={"email": "user@example.com", "password": VALID_PASSWORD}
    )

    user = await db_session.scalar(select(User).where(User.email == "user@example.com"))
    assert user is not None
    assert user.hashed_password != VALID_PASSWORD

    group_name = await db_session.scalar(
        select(UserGroup.name).where(UserGroup.id == user.group_id)
    )
    assert group_name == UserGroupEnum.USER


async def test_register_creates_hashed_activation_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post(
        REGISTER_URL, json={"email": "user@example.com", "password": VALID_PASSWORD}
    )
    user_id = response.json()["id"]

    token = await db_session.scalar(
        select(ActivationToken).where(ActivationToken.user_id == user_id)
    )
    assert token is not None
    assert len(token.token_hash) == 64

    expected_expires_at = datetime.now(UTC) + timedelta(
        hours=get_settings().ACTIVATION_TOKEN_EXPIRE_HOURS
    )
    assert abs(token.expires_at - expected_expires_at) < timedelta(minutes=1)


@pytest.mark.parametrize(
    "duplicate_email",
    ["user@example.com", "USER@example.com"],
    ids=["same_case", "different_case"],
)
async def test_register_rejects_existing_email(
    client: AsyncClient, duplicate_email: str
) -> None:
    await client.post(
        REGISTER_URL, json={"email": "user@example.com", "password": VALID_PASSWORD}
    )

    response = await client.post(
        REGISTER_URL, json={"email": duplicate_email, "password": VALID_PASSWORD}
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "User with this email already exists."}


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "password": VALID_PASSWORD},
        {"email": "user@example.com", "password": "weakpass1!"},
        {"email": "user@example.com"},
    ],
    ids=["invalid_email", "weak_password", "missing_password"],
)
async def test_register_rejects_invalid_payload(
    client: AsyncClient, payload: dict[str, str]
) -> None:
    response = await client.post(REGISTER_URL, json=payload)

    assert response.status_code == 422
