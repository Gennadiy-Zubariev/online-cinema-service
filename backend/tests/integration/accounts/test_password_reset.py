from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import PasswordResetToken, User
from src.accounts.security import hash_token
from src.config.settings import get_settings
from tests.integration.conftest import USER_PASSWORD, CreateUser

LOGIN_URL = "/api/v1/accounts/login"
REQUEST_URL = "/api/v1/accounts/password-reset/request"
COMPLETE_URL = "/api/v1/accounts/password-reset/complete"
RAW_RESET_TOKEN = "raw-reset-token"
NEW_PASSWORD = "NewStrongPass2@"
NEUTRAL_RESPONSE = {
    "message": "If the account exists and is active, "
    "a password reset email has been sent."
}
INVALID_RESET_TOKEN = {
    "detail": "Invalid or expired password reset token. Please request a new one."
}


async def add_reset_token(
    db_session: AsyncSession, user: User, expires_in: timedelta = timedelta(hours=1)
) -> None:
    db_session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(RAW_RESET_TOKEN),
            expires_at=datetime.now(UTC) + expires_in,
        )
    )
    await db_session.commit()


async def reset_tokens(db_session: AsyncSession) -> list[PasswordResetToken]:
    return list((await db_session.scalars(select(PasswordResetToken))).all())


async def login_status(client: AsyncClient, password: str) -> int:
    response = await client.post(
        LOGIN_URL, json={"email": "user@example.com", "password": password}
    )
    return response.status_code


# --- request ---


async def test_request_creates_token_and_sends_email(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user: CreateUser,
    send_password_reset_email_mock: MagicMock,
) -> None:
    user = await create_user(is_active=True)

    response = await client.post(REQUEST_URL, json={"email": user.email})

    assert response.status_code == 200
    assert response.json() == NEUTRAL_RESPONSE

    send_password_reset_email_mock.delay.assert_called_once()
    email, raw_token = send_password_reset_email_mock.delay.call_args.args
    assert email == user.email

    tokens = await reset_tokens(db_session)
    assert len(tokens) == 1
    assert tokens[0].user_id == user.id
    assert tokens[0].token_hash == hash_token(raw_token)
    expected_expires_at = datetime.now(UTC) + timedelta(
        hours=get_settings().PASSWORD_RESET_TOKEN_EXPIRE_HOURS
    )
    assert abs(tokens[0].expires_at - expected_expires_at) < timedelta(minutes=1)


async def test_request_twice_replaces_token(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user: CreateUser,
    send_password_reset_email_mock: MagicMock,
) -> None:
    # Covers DELETE + flush + INSERT with unique(user_id) in one transaction.
    user = await create_user(is_active=True)
    await add_reset_token(db_session, user)

    response = await client.post(REQUEST_URL, json={"email": user.email})

    assert response.status_code == 200
    _, raw_token = send_password_reset_email_mock.delay.call_args.args
    tokens = await reset_tokens(db_session)
    assert len(tokens) == 1
    assert tokens[0].token_hash == hash_token(raw_token)


async def test_request_is_case_insensitive_for_email(
    client: AsyncClient,
    create_user: CreateUser,
    send_password_reset_email_mock: MagicMock,
) -> None:
    await create_user(email="user@example.com", is_active=True)

    await client.post(REQUEST_URL, json={"email": "USER@Example.com"})

    send_password_reset_email_mock.delay.assert_called_once()


@pytest.mark.parametrize("case", ["unknown_email", "inactive_user"])
async def test_request_returns_same_response_without_sending_email(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user: CreateUser,
    send_password_reset_email_mock: MagicMock,
    case: str,
) -> None:
    # ТЗ: only for a registered AND active email; don't leak which one failed.
    await create_user(is_active=False)
    email = "nobody@example.com" if case == "unknown_email" else "user@example.com"

    response = await client.post(REQUEST_URL, json={"email": email})

    assert response.status_code == 200
    assert response.json() == NEUTRAL_RESPONSE
    send_password_reset_email_mock.delay.assert_not_called()
    assert await reset_tokens(db_session) == []


async def test_request_rejects_invalid_email(client: AsyncClient) -> None:
    response = await client.post(REQUEST_URL, json={"email": "not-an-email"})

    assert response.status_code == 422


# --- complete ---


async def test_complete_sets_new_password(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    user = await create_user(is_active=True)
    await add_reset_token(db_session, user)

    response = await client.post(
        COMPLETE_URL, json={"token": RAW_RESET_TOKEN, "new_password": NEW_PASSWORD}
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Password has been reset successfully."}
    assert await login_status(client, USER_PASSWORD) == 401
    assert await login_status(client, NEW_PASSWORD) == 200


async def test_complete_deletes_token_so_it_cannot_be_reused(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    user = await create_user(is_active=True)
    await add_reset_token(db_session, user)
    payload = {"token": RAW_RESET_TOKEN, "new_password": NEW_PASSWORD}

    await client.post(COMPLETE_URL, json=payload)
    response = await client.post(COMPLETE_URL, json=payload)

    assert await reset_tokens(db_session) == []
    assert response.status_code == 400
    assert response.json() == INVALID_RESET_TOKEN


async def test_complete_rejects_unknown_token(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    user = await create_user(is_active=True)
    await add_reset_token(db_session, user)

    response = await client.post(
        COMPLETE_URL, json={"token": "unknown-token", "new_password": NEW_PASSWORD}
    )

    assert response.status_code == 400
    assert response.json() == INVALID_RESET_TOKEN
    assert await login_status(client, USER_PASSWORD) == 200


async def test_complete_rejects_expired_token(
    client: AsyncClient, db_session: AsyncSession, create_user: CreateUser
) -> None:
    user = await create_user(is_active=True)
    await add_reset_token(db_session, user, expires_in=timedelta(seconds=-1))

    response = await client.post(
        COMPLETE_URL, json={"token": RAW_RESET_TOKEN, "new_password": NEW_PASSWORD}
    )

    assert response.status_code == 400
    assert response.json() == INVALID_RESET_TOKEN
    assert await login_status(client, USER_PASSWORD) == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"token": RAW_RESET_TOKEN, "new_password": "weakpass1!"},
        {"token": "", "new_password": NEW_PASSWORD},
        {"token": "x" * 129, "new_password": NEW_PASSWORD},
        {"token": RAW_RESET_TOKEN},
    ],
    ids=["weak_password", "empty_token", "too_long_token", "missing_password"],
)
async def test_complete_rejects_invalid_payload(
    client: AsyncClient,
    db_session: AsyncSession,
    create_user: CreateUser,
    payload: dict[str, str],
) -> None:
    user = await create_user(is_active=True)
    await add_reset_token(db_session, user)

    response = await client.post(COMPLETE_URL, json=payload)

    assert response.status_code == 422
    assert len(await reset_tokens(db_session)) == 1
