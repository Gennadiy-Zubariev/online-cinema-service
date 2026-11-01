from datetime import UTC, datetime, timedelta

from fastapi.concurrency import run_in_threadpool
from psycopg.errors import UniqueViolation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.accounts.exceptions import (
    UserAlreadyExistsError,
    ActivationTokenExpiredError,
    InvalidActivationTokenError,
)
from src.accounts.models import ActivationToken, User, UserGroup, UserGroupEnum
from src.accounts.schemas import UserRegisterRequest
from src.accounts.security import generate_token, hash_password, hash_token
from src.config.settings import Settings
from src.tasks.emails import send_activation_email


async def register_user(
    db: AsyncSession, data: UserRegisterRequest, settings: Settings
) -> User:
    existing_user = await db.scalar(select(User).where(User.email == data.email))
    if existing_user is not None:
        raise UserAlreadyExistsError(data.email)

    result = await db.execute(
        select(UserGroup).where(UserGroup.name == UserGroupEnum.USER)
    )
    group = result.scalar_one()

    hashed_password = await run_in_threadpool(hash_password, data.password)
    user = User(email=data.email, hashed_password=hashed_password, group=group)

    raw_token = generate_token()
    user.activation_token = ActivationToken(
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(UTC)
        + timedelta(hours=settings.ACTIVATION_TOKEN_EXPIRE_HOURS),
    )

    db.add(user)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        if isinstance(error.orig, UniqueViolation):
            raise UserAlreadyExistsError(data.email) from error
        raise  # not an email conflict — propagate as 500

    send_activation_email.delay(user.email, raw_token)
    return user


async def activate_account(db: AsyncSession, token: str) -> User:
    hashed_token = hash_token(token)
    activation_token = await db.scalar(
        select(ActivationToken)
        .where(ActivationToken.token_hash == hashed_token)
        .options(joinedload(ActivationToken.user))
    )
    if activation_token is None:
        raise InvalidActivationTokenError()
    if activation_token.expires_at < datetime.now(UTC):
        raise ActivationTokenExpiredError()
    user = activation_token.user
    user.is_active = True
    await db.delete(activation_token)
    await db.commit()
    return user
