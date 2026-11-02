from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import ActivationToken
from tests.integration.accounts.conftest import RAW_ACTIVATION_TOKEN, CreateUser

ACTIVATION_URL = "/api/v1/accounts/activation"


async def test_activation_activates_user(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    user = await create_user()

    response = await client.post(ACTIVATION_URL, json={"token": RAW_ACTIVATION_TOKEN})

    assert response.status_code == 200
    assert response.json() == {"message": "Account activated successfully."}
    await db_session.refresh(user)
    assert user.is_active is True


async def test_activation_deletes_used_token(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    user = await create_user()

    await client.post(ACTIVATION_URL, json={"token": RAW_ACTIVATION_TOKEN})

    token = await db_session.scalar(
        select(ActivationToken).where(ActivationToken.user_id == user.id)
    )
    assert token is None


async def test_activation_token_cannot_be_reused(
    client: AsyncClient, create_user: CreateUser
) -> None:
    await create_user()
    await client.post(ACTIVATION_URL, json={"token": RAW_ACTIVATION_TOKEN})

    response = await client.post(ACTIVATION_URL, json={"token": RAW_ACTIVATION_TOKEN})

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid or already used activation token."}


async def test_activation_rejects_unknown_token(
    client: AsyncClient, create_user: CreateUser
) -> None:
    await create_user()

    response = await client.post(ACTIVATION_URL, json={"token": "unknown-token"})

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid or already used activation token."}


async def test_activation_rejects_expired_token(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    user = await create_user(token_expires_in=timedelta(seconds=-1))

    response = await client.post(ACTIVATION_URL, json={"token": RAW_ACTIVATION_TOKEN})

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Activation token has expired. Please request a new one."
    }
    await db_session.refresh(user)
    assert user.is_active is False


@pytest.mark.parametrize(
    "payload",
    [{}, {"token": ""}, {"token": "x" * 129}],
    ids=["missing_token", "empty_token", "too_long_token"],
)
async def test_activation_rejects_invalid_payload(
    client: AsyncClient, payload: dict[str, str]
) -> None:
    response = await client.post(ACTIVATION_URL, json=payload)

    assert response.status_code == 422
