from datetime import UTC, datetime, timedelta

from fastapi.concurrency import run_in_threadpool
from psycopg.errors import UniqueViolation
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.accounts.exceptions import (
    UserAlreadyExistsError,
    ActivationTokenExpiredError,
    InvalidActivationTokenError,
    InvalidCredentialsError,
    UserNotActiveError,
    InvalidRefreshTokenError,
    IncorrectPasswordError,
    InvalidPasswordResetTokenError,
)
from src.accounts.models import (
    ActivationToken,
    User,
    UserGroup,
    UserGroupEnum,
    RefreshToken,
    PasswordResetToken,
)
from src.accounts.schemas import (
    UserRegisterRequest,
    ResendActivationRequest,
    LoginRequest,
    ChangePasswordRequest,
    PasswordResetRequest,
    PasswordResetCompleteRequest,
)
from src.accounts.security import (
    generate_token,
    hash_password,
    hash_token,
    create_access_token,
    verify_password,
    create_refresh_token,
    decode_refresh_token,
)
from src.config.settings import Settings
from src.tasks.emails import send_activation_email, send_password_reset_email


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


async def resend_activation_token(
    db: AsyncSession,
    data: ResendActivationRequest,
    settings: Settings,
) -> None:
    user = await db.scalar(
        select(User)
        .where(User.email == data.email)
        .options(joinedload(User.activation_token))
    )
    if not user or user.is_active:
        return
    activation_token = user.activation_token
    if activation_token is not None:
        await db.delete(activation_token)
        await db.flush()
    raw_token = generate_token()
    user.activation_token = ActivationToken(
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(UTC)
        + timedelta(hours=settings.ACTIVATION_TOKEN_EXPIRE_HOURS),
    )
    await db.commit()
    send_activation_email.delay(user.email, raw_token)


async def login_user(
    db: AsyncSession,
    data: LoginRequest,
    settings: Settings,
) -> tuple[str, str]:
    user = await db.scalar(select(User).where(User.email == data.email))
    if user is None:
        raise InvalidCredentialsError()

    is_password_valid = await run_in_threadpool(
        verify_password, data.password, user.hashed_password
    )
    if not is_password_valid:
        raise InvalidCredentialsError()
    if not user.is_active:
        raise UserNotActiveError()

    refresh_token = create_refresh_token(user_id=user.id, settings=settings)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    await db.commit()
    return create_access_token(user_id=user.id, settings=settings), refresh_token


async def logout_user(db: AsyncSession, refresh_token: str) -> None:
    await db.execute(
        delete(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token))
    )
    await db.commit()


async def refresh_access_token(
    db: AsyncSession, refresh_token: str, settings: Settings
) -> str:
    user_id = decode_refresh_token(token=refresh_token, settings=settings)
    token_id = await db.scalar(
        select(RefreshToken.id).where(
            RefreshToken.token_hash == hash_token(refresh_token)
        )
    )
    if token_id is None:
        raise InvalidRefreshTokenError()
    return create_access_token(user_id=user_id, settings=settings)


async def change_user_password(
    db: AsyncSession,
    current_user: User,
    data: ChangePasswordRequest,
) -> None:
    is_old_password_valid = await run_in_threadpool(
        verify_password, data.old_password, current_user.hashed_password
    )
    if not is_old_password_valid:
        raise IncorrectPasswordError()

    current_user.hashed_password = await run_in_threadpool(
        hash_password, data.new_password
    )
    await db.commit()


async def request_password_reset(
    db: AsyncSession,
    data: PasswordResetRequest,
    settings: Settings,
) -> None:
    user = await db.scalar(
        select(User)
        .where(User.email == data.email)
        .options(joinedload(User.password_reset_token))
    )
    if user is None or not user.is_active:
        return
    if user.password_reset_token is not None:
        await db.delete(user.password_reset_token)
        await db.flush()

    raw_token = generate_token()
    user.password_reset_token = PasswordResetToken(
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(UTC)
        + timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS),
    )
    await db.commit()
    send_password_reset_email.delay(user.email, raw_token)


async def reset_password(db: AsyncSession, data: PasswordResetCompleteRequest) -> None:
    reset_token = await db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == hash_token(data.token))
        .options(joinedload(PasswordResetToken.user))
    )
    if reset_token is None or reset_token.expires_at < datetime.now(UTC):
        raise InvalidPasswordResetTokenError()

    reset_token.user.hashed_password = await run_in_threadpool(
        hash_password, data.new_password
    )
    await db.delete(reset_token)
    await db.commit()
