from fastapi import APIRouter
from starlette import status

from src.accounts.models import User
from src.accounts.schemas import (
    UserResponse,
    UserRegisterRequest,
    ActivationRequest,
    MessageResponse,
)
from src.accounts.service import register_user, activate_account
from src.config.settings import SettingsDep
from src.database.session import DbSession

router = APIRouter(prefix="/accounts", tags=["accounts"])


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
