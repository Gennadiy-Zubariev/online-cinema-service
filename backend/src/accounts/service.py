from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.concurrency import run_in_threadpool
from psycopg.errors import UniqueViolation
from sqlalchemy import select, delete, func
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
    UserNotFoundError,
    UserDeactivatedError,
    SelfDeactivationError,
)
from src.accounts.models import (
    ActivationToken,
    User,
    UserGroup,
    UserGroupEnum,
    RefreshToken,
    PasswordResetToken,
    UserProfile,
)
from src.accounts.schemas import (
    UserRegisterRequest,
    ResendActivationRequest,
    LoginRequest,
    ChangePasswordRequest,
    PasswordResetRequest,
    PasswordResetCompleteRequest,
    ProfileUpdateRequest,
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
from src.storage.client import upload_file, delete_file
from src.storage.images import validate_image
from src.tasks.emails import send_activation_email, send_password_reset_email

MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2 MB


async def _issue_refresh_token(
    db: AsyncSession, user_id: int, settings: Settings
) -> str:
    """Create a refresh JWT and store its hash; the caller commits."""
    refresh_token = create_refresh_token(user_id=user_id, settings=settings)
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_token(refresh_token),
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    return refresh_token


async def register_user(
    db: AsyncSession, data: UserRegisterRequest, settings: Settings
) -> User:
    """Create an inactive user in the USER group and send the activation email.

    Raises UserAlreadyExistsError if the email is taken, including a concurrent
    registration caught as UniqueViolation on commit. The email task is queued
    only after commit.
    """
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
        raise

    send_activation_email.delay(user.email, raw_token)
    return user


async def activate_account(db: AsyncSession, token: str) -> User:
    """Activate the user by a raw activation token and delete the token.

    Raises InvalidActivationTokenError or ActivationTokenExpiredError.
    An expired token is kept: resending replaces it, celery-beat cleans up the rest.
    """
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
    """Replace the activation token and send the email again.

    Unknown, already active or deactivated email -> silent return (no user
    enumeration; a deactivated user must not reactivate himself).
    The old token is flushed out first: otherwise the unit of work inserts
    the new one before deleting the old one and hits the unique user_id.
    """
    user = await db.scalar(
        select(User)
        .where(User.email == data.email)
        .options(joinedload(User.activation_token))
    )
    if not user or user.is_active or user.deactivated_at is not None:
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
    """Check credentials and return (access token, refresh token).

    Raises InvalidCredentialsError for an unknown email or a wrong password,
    UserDeactivatedError / UserNotActiveError only after the password matched.
    Stores the refresh
    token hash; tokens of other devices are kept.
    """
    user = await db.scalar(select(User).where(User.email == data.email))
    if user is None:
        raise InvalidCredentialsError()

    is_password_valid = await run_in_threadpool(
        verify_password, data.password, user.hashed_password
    )
    if not is_password_valid:
        raise InvalidCredentialsError()
    if user.deactivated_at is not None:
        raise UserDeactivatedError()
    if not user.is_active:
        raise UserNotActiveError()

    refresh_token = await _issue_refresh_token(
        db=db, user_id=user.id, settings=settings
    )
    await db.commit()
    return create_access_token(user_id=user.id, settings=settings), refresh_token


async def logout_user(db: AsyncSession, refresh_token: str) -> None:
    """Revoke one refresh token by its hash; unknown tokens are ignored."""
    await db.execute(
        delete(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token))
    )
    await db.commit()


async def rotate_refresh_token(
    db: AsyncSession, refresh_token: str, settings: Settings
) -> tuple[str, str]:
    """Revoke the refresh token and return a new (access, refresh) pair.

    A validly signed token that is no longer in DB was already rotated or
    logged out: it may be stolen, so all refresh tokens of its user are
    revoked (every device has to log in again). DELETE ... RETURNING is
    atomic: of two concurrent requests with the same token only one gets
    the row. Raises InvalidRefreshTokenError (also for a deactivated user).
    """
    user_id = decode_refresh_token(token=refresh_token, settings=settings)
    revoked_id = await db.scalar(
        delete(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(refresh_token))
        .returning(RefreshToken.id)
    )
    if revoked_id is None:
        await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
        await db.commit()
        raise InvalidRefreshTokenError()

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
        await db.commit()
        raise InvalidRefreshTokenError()

    new_refresh_token = await _issue_refresh_token(
        db=db, user_id=user_id, settings=settings
    )
    await db.commit()
    return create_access_token(user_id=user_id, settings=settings), new_refresh_token


async def change_user_password(
    db: AsyncSession,
    current_user: User,
    data: ChangePasswordRequest,
) -> None:
    """Set a new password after checking the old one.

    Raises IncorrectPasswordError (400, not 401: the access token is valid).
    """
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
    """Create a password reset token and email it.

    Unknown or inactive email -> silent return (no user enumeration).
    A previous token is replaced (flushed out first, as in resending activation).
    """
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
    """Set a new password by a raw reset token; the token is single-use.

    Raises InvalidPasswordResetTokenError for unknown and expired tokens alike.
    """
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


async def change_user_group(
    db: AsyncSession, user_id: int, group_name: UserGroupEnum
) -> None:
    """Move the user to another group; raises UserNotFoundError."""
    user = await db.get(User, user_id)
    if user is None:
        raise UserNotFoundError()

    result = await db.execute(select(UserGroup).where(UserGroup.name == group_name))
    user.group = result.scalar_one()
    await db.commit()


async def activate_user_manually(db: AsyncSession, user_id: int) -> None:
    """Activate the user (admin action) and delete the activation token.

    Also lifts a deactivation. Refresh tokens issued before the user became
    inactive are deleted, so old sessions do not come back to life.
    Idempotent for an active user (his sessions stay); raises UserNotFoundError.
    """
    user = await db.scalar(
        select(User)
        .where(User.id == user_id)
        .options(joinedload(User.activation_token))
    )
    if user is None:
        raise UserNotFoundError()
    was_active = user.is_active
    user.is_active = True
    user.deactivated_at = None
    if user.activation_token is not None:
        await db.delete(user.activation_token)
    if not was_active:
        await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    await db.commit()


async def deactivate_user_manually(
    db: AsyncSession, user_id: int, admin_id: int
) -> None:
    """Deactivate the user (admin action) and end all his sessions.

    Deletes refresh tokens (every device is logged out) and the activation
    token; deactivated_at blocks resending the activation email, so only an
    admin can activate the user again. Access tokens stop working at once:
    get_current_user checks is_active. Idempotent (the first deactivation
    time is kept). Raises SelfDeactivationError or UserNotFoundError.
    """
    if user_id == admin_id:
        raise SelfDeactivationError()
    user = await db.scalar(
        select(User)
        .where(User.id == user_id)
        .options(joinedload(User.activation_token))
    )
    if user is None:
        raise UserNotFoundError()
    user.is_active = False
    if user.deactivated_at is None:
        user.deactivated_at = datetime.now(UTC)
    if user.activation_token is not None:
        await db.delete(user.activation_token)
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    await db.commit()


async def list_users(
    db: AsyncSession, page: int, page_size: int
) -> tuple[list[User], int]:
    """Return (users on the page, total number of users)."""
    total = await db.scalar(select(func.count()).select_from(User))
    result = await db.scalars(
        select(User)
        .options(joinedload(User.group))
        .order_by(User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.all()), total or 0


async def get_user_profile(db: AsyncSession, user_id: int) -> UserProfile | None:
    """Return the user's profile, or None if it has not been created yet."""
    return await db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))


async def update_user_profile(
    db: AsyncSession, user_id: int, data: ProfileUpdateRequest
) -> UserProfile:
    """Create or partially update the user's profile.

    Only fields sent in the request change; an explicit null clears a field.
    """
    profile = await get_user_profile(db=db, user_id=user_id)
    if profile is None:
        profile = UserProfile(user_id=user_id)
        db.add(profile)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    await db.commit()
    return profile


async def update_user_avatar(
    db: AsyncSession, user_id: int, data: bytes
) -> UserProfile:
    """Validate and upload a new avatar, then delete the old file.

    Raises UnsupportedImageTypeError / ImageTooLargeError before touching the DB.
    Order upload -> commit -> delete old: a failure leaves at most an orphan
    file in S3, never a profile pointing to a missing one.
    """
    content_type, extension = validate_image(data, MAX_AVATAR_SIZE)

    profile = await get_user_profile(db=db, user_id=user_id)
    if profile is None:
        profile = UserProfile(user_id=user_id)
        db.add(profile)

    old_key = profile.avatar
    new_key = f"avatars/{user_id}/{uuid4().hex}.{extension}"
    await run_in_threadpool(upload_file, new_key, data, content_type)
    profile.avatar = new_key
    await db.commit()

    if old_key is not None:
        await run_in_threadpool(delete_file, old_key)
    return profile
