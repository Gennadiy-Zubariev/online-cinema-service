from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import ActivationToken
from src.accounts.security import hash_token
from src.config.settings import get_settings
from tests.integration.accounts.conftest import RAW_ACTIVATION_TOKEN, CreateUser

RESEND_URL = "/api/v1/accounts/activation/resend"
NEUTRAL_RESPONSE = {
    "message": "If the account exists and is not activated, "
    "a new activation email has been sent."
}


@pytest.mark.parametrize(
    "token_expires_in",
    [timedelta(hours=24), timedelta(seconds=-1), None],
    ids=["valid_token", "expired_token", "no_token"],
)
async def test_resend_replaces_token_for_inactive_user(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user: CreateUser,
    send_activation_email_mock: MagicMock,
    token_expires_in: timedelta | None,
) -> None:
    # "valid_token" covers DELETE + INSERT with unique(user_id) in one transaction.
    user = await create_user(token_expires_in=token_expires_in)

    response = await client.post(RESEND_URL, json={"email": user.email})

    assert response.status_code == 200
    assert response.json() == NEUTRAL_RESPONSE

    send_activation_email_mock.delay.assert_called_once()
    email, raw_token = send_activation_email_mock.delay.call_args.args
    assert email == user.email
    assert raw_token != RAW_ACTIVATION_TOKEN

    tokens = (
        await db_session.scalars(
            select(ActivationToken).where(ActivationToken.user_id == user.id)
        )
    ).all()
    assert len(tokens) == 1
    assert tokens[0].token_hash == hash_token(raw_token)

    expected_expires_at = datetime.now(UTC) + timedelta(
        hours=get_settings().ACTIVATION_TOKEN_EXPIRE_HOURS
    )
    assert abs(tokens[0].expires_at - expected_expires_at) < timedelta(minutes=1)


async def test_resend_is_case_insensitive_for_email(
    client: AsyncClient,
    create_user: CreateUser,
    send_activation_email_mock: MagicMock,
) -> None:
    await create_user(email="user@example.com")

    await client.post(RESEND_URL, json={"email": "USER@Example.com"})

    send_activation_email_mock.delay.assert_called_once()


async def test_resend_for_unknown_email_returns_same_response(
    client: AsyncClient, send_activation_email_mock: MagicMock
) -> None:
    response = await client.post(RESEND_URL, json={"email": "nobody@example.com"})

    assert response.status_code == 200
    assert response.json() == NEUTRAL_RESPONSE
    send_activation_email_mock.delay.assert_not_called()


async def test_resend_for_active_user_returns_same_response(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user: CreateUser,
    send_activation_email_mock: MagicMock,
) -> None:
    user = await create_user(is_active=True, token_expires_in=None)

    response = await client.post(RESEND_URL, json={"email": user.email})

    assert response.status_code == 200
    assert response.json() == NEUTRAL_RESPONSE
    send_activation_email_mock.delay.assert_not_called()
    token = await db_session.scalar(
        select(ActivationToken).where(ActivationToken.user_id == user.id)
    )
    assert token is None


async def test_resend_rejects_invalid_email(client: AsyncClient) -> None:
    response = await client.post(RESEND_URL, json={"email": "not-an-email"})

    assert response.status_code == 422
