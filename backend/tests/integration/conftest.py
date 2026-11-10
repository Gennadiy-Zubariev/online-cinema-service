from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.accounts.models import ActivationToken, User, UserGroup, UserGroupEnum
from src.accounts.security import hash_password, hash_token

RAW_ACTIVATION_TOKEN = "raw-activation-token"
USER_PASSWORD = "StrongPass1!"

CreateUser = Callable[..., Awaitable[User]]


@pytest.fixture
def create_user(db_session: AsyncSession) -> CreateUser:
    """Factory: save a user (optionally with an activation token) directly in DB.

    Bypasses the register endpoint, so tests control `is_active` and token expiry.
    The password is always `USER_PASSWORD` (real argon2 hash, so login works).
    `token_expires_in=None` creates the user without an activation token.
    """

    async def _create_user(
        email: str = "user@example.com",
        is_active: bool = False,
        token_expires_in: timedelta | None = timedelta(hours=24),
        group: UserGroupEnum = UserGroupEnum.USER,
    ) -> User:
        user_group = await db_session.scalar(
            select(UserGroup).where(UserGroup.name == group)
        )
        user = User(
            email=email,
            hashed_password=hash_password(USER_PASSWORD),
            is_active=is_active,
            group=user_group,
        )
        if token_expires_in is not None:
            user.activation_token = ActivationToken(
                token_hash=hash_token(RAW_ACTIVATION_TOKEN),
                expires_at=datetime.now(UTC) + token_expires_in,
            )
        db_session.add(user)
        await db_session.commit()
        return user

    return _create_user
