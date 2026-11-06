from typing import Annotated

from fastapi import APIRouter, Response, status, Cookie, Depends, UploadFile

from src.accounts.dependencies import CurrentUser, get_current_admin
from src.accounts.exceptions import InvalidRefreshTokenError
from src.accounts.models import User, UserProfile
from src.accounts.schemas import (
    UserResponse,
    UserRegisterRequest,
    ActivationRequest,
    MessageResponse,
    ResendActivationRequest,
    AccessTokenResponse,
    LoginRequest,
    ChangePasswordRequest,
    PasswordResetRequest,
    PasswordResetCompleteRequest,
    UserGroupUpdateRequest,
    UserListResponse,
    UserAdminResponse,
    ProfileResponse,
    ProfileUpdateRequest,
)
from src.accounts.service import (
    register_user,
    activate_account,
    resend_activation_token,
    login_user,
    logout_user,
    refresh_access_token,
    change_user_password,
    request_password_reset,
    reset_password,
    change_user_group,
    activate_user_manually,
    list_users,
    get_user_profile,
    update_user_profile,
    update_user_avatar,
    MAX_AVATAR_SIZE,
)
from src.common.pagination import Pagination
from src.config.settings import SettingsDep
from src.database.session import DbSession
from src.storage.client import get_file_url

router = APIRouter(prefix="/accounts", tags=["accounts"])

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/accounts"


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    db: DbSession, data: UserRegisterRequest, settings: SettingsDep
) -> User:
    """Register a new user and send an activation email.

    The account stays inactive until activated (link valid for 24 hours).
    Returns 409 if the email is already registered.
    """
    return await register_user(db=db, data=data, settings=settings)


@router.post(
    "/activation",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
)
async def activate(db: DbSession, data: ActivationRequest) -> MessageResponse:
    """Activate an account with the token from the activation email.

    Returns 400 if the token is unknown, already used or expired.
    """
    await activate_account(db=db, token=data.token)
    return MessageResponse(message="Account activated successfully.")


@router.post(
    "/activation/resend", response_model=MessageResponse, status_code=status.HTTP_200_OK
)
async def resend_activation(
    db: DbSession,
    data: ResendActivationRequest,
    settings: SettingsDep,
) -> MessageResponse:
    """Send a new activation email (new token valid for 24 hours).

    Always returns the same response, so it does not reveal whether
    the email is registered or already active.
    """
    await resend_activation_token(db=db, data=data, settings=settings)
    return MessageResponse(
        message="If the account exists and is not activated, "
        "a new activation email has been sent."
    )


@router.post(
    "/login",
    response_model=AccessTokenResponse,
    status_code=status.HTTP_200_OK,
)
async def login(
    db: DbSession,
    data: LoginRequest,
    settings: SettingsDep,
    response: Response,
) -> AccessTokenResponse:
    """Log in and receive a pair of JWT tokens.

    The access token is returned in the body; the refresh token is set
    as an httpOnly cookie. Returns 401 for wrong credentials and 403
    if the account is not activated.
    """
    access_token, refresh_token = await login_user(db=db, data=data, settings=settings)
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )
    return AccessTokenResponse(access_token=access_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def logout(
    db: DbSession,
    settings: SettingsDep,
    response: Response,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> None:
    """Log out: revoke the refresh token from the cookie and clear it.

    Idempotent: returns 204 even without a cookie or with an unknown token.
    """
    if refresh_token is not None:
        await logout_user(db=db, refresh_token=refresh_token)
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
    )


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    status_code=status.HTTP_200_OK,
)
async def refresh(
    db: DbSession,
    settings: SettingsDep,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> AccessTokenResponse:
    """Get a new access token using the refresh token from the cookie.

    Returns 401 if the refresh token is missing, invalid, expired
    or revoked by logout.
    """
    if refresh_token is None:
        raise InvalidRefreshTokenError()
    access_token = await refresh_access_token(
        db=db, refresh_token=refresh_token, settings=settings
    )

    return AccessTokenResponse(access_token=access_token)


@router.post(
    "/change-password", status_code=status.HTTP_200_OK, response_model=MessageResponse
)
async def change_password(
    db: DbSession, current_user: CurrentUser, data: ChangePasswordRequest
) -> MessageResponse:
    """Change the current user's password (old password required).

    Returns 400 if the old password is incorrect.
    """
    await change_user_password(db=db, current_user=current_user, data=data)
    return MessageResponse(message="Password changed successfully.")


@router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
)
async def password_reset_request(
    db: DbSession, data: PasswordResetRequest, settings: SettingsDep
) -> MessageResponse:
    """Send a password reset email (link valid for 1 hour).

    Only for registered and active accounts. Always returns the same
    response, so it does not reveal whether the email exists.
    """
    await request_password_reset(db=db, data=data, settings=settings)
    return MessageResponse(
        message="If the account exists and is active, "
        "a password reset email has been sent."
    )


@router.post(
    "/password-reset/complete",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
)
async def password_reset_complete(
    db: DbSession,
    data: PasswordResetCompleteRequest,
) -> MessageResponse:
    """Set a new password with the token from the password reset email.

    The token can be used once. Returns 400 if it is unknown or expired.
    """
    await reset_password(db=db, data=data)
    return MessageResponse(message="Password has been reset successfully.")


@router.patch(
    "/users/{user_id}/group",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_admin)],
)
async def update_user_group(
    user_id: int, data: UserGroupUpdateRequest, db: DbSession
) -> MessageResponse:
    """Change a user's group (admin only).

    Returns 404 if the user does not exist.
    """
    await change_user_group(db=db, user_id=user_id, group_name=data.group)
    return MessageResponse(message="User group updated.")


@router.post(
    "/users/{user_id}/activate",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_admin)],
)
async def activate_user(user_id: int, db: DbSession) -> MessageResponse:
    """Manually activate a user's account (admin only).

    Removes the pending activation token. Already active users
    get 200 as well. Returns 404 if the user does not exist.
    """
    await activate_user_manually(db=db, user_id=user_id)
    return MessageResponse(message="User activated.")


@router.get(
    "/users",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_admin)],
)
async def list_all_users(db: DbSession, pagination: Pagination) -> UserListResponse:
    """List all users with their groups, ordered by id (admin only)."""
    users, total = await list_users(
        db=db, page=pagination.page, page_size=pagination.page_size
    )
    return UserListResponse(
        items=[UserAdminResponse.model_validate(user) for user in users],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


def _to_profile_response(profile: UserProfile | None) -> ProfileResponse:
    if profile is None:
        return ProfileResponse()
    return ProfileResponse(
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar_url=get_file_url(profile.avatar) if profile.avatar else None,
    )


@router.get(
    "/profile",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
)
async def get_profile(db: DbSession, current_user: CurrentUser) -> ProfileResponse:
    """Get the current user's profile.

    Returns an empty profile (all fields null) if it was never filled in.
    """
    profile = await get_user_profile(db=db, user_id=current_user.id)
    return _to_profile_response(profile)


@router.patch(
    "/profile",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
)
async def update_profile(
    data: ProfileUpdateRequest, db: DbSession, current_user: CurrentUser
) -> ProfileResponse:
    """Partially update the current user's profile.

    Only the sent fields change; an explicit null clears a field.
    The profile is created on the first update.
    """
    profile = await update_user_profile(db=db, user_id=current_user.id, data=data)
    return _to_profile_response(profile)


@router.put(
    "/profile/avatar",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
)
async def update_profile_avatar(
    db: DbSession, current_user: CurrentUser, file: UploadFile
) -> ProfileResponse:
    """Upload or replace the current user's avatar.

    Accepts JPEG, PNG or WebP up to 2 MB (415 / 413 otherwise).
    The previous avatar file is deleted.
    """
    data = await file.read(MAX_AVATAR_SIZE + 1)
    profile = await update_user_avatar(
        db=db, user_id=current_user.id, data=data, content_type=file.content_type
    )
    return _to_profile_response(profile)
