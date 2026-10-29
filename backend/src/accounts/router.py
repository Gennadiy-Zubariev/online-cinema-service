from fastapi import APIRouter
from starlette import status

from src.accounts.models import User
from src.accounts.schemas import UserResponse, UserRegisterRequest
from src.accounts.service import register_user
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
