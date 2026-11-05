from typing import Annotated

from fastapi import APIRouter, Response, status, Cookie, Depends, Query, UploadFile

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
    return await register_user(db=db, data=data, settings=settings)


@router.post(
    "/activation",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
)
async def activate(db: DbSession, data: ActivationRequest) -> MessageResponse:
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
    await change_user_group(db=db, user_id=user_id, group_name=data.group)
    return MessageResponse(message="User group updated.")


@router.post(
    "/users/{user_id}/activate",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_admin)],
)
async def activate_user(user_id: int, db: DbSession) -> MessageResponse:
    await activate_user_manually(db=db, user_id=user_id)
    return MessageResponse(message="User activated.")


@router.get(
    "/users",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_admin)],
)
async def list_all_users(
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> UserListResponse:
    users, total = await list_users(db=db, page=page, page_size=page_size)
    return UserListResponse(
        items=[UserAdminResponse.model_validate(user) for user in users],
        total=total,
        page=page,
        page_size=page_size,
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
    data = await file.read(MAX_AVATAR_SIZE + 1)
    profile = await update_user_avatar(
        db=db, user_id=current_user.id, data=data, content_type=file.content_type
    )
    return _to_profile_response(profile)
