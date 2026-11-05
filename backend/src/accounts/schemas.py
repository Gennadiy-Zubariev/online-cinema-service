from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from src.accounts.models import UserGroupEnum
from src.accounts.validators import validate_password_strength

NormalizedEmail = Annotated[EmailStr, AfterValidator(str.lower)]
StrongPassword = Annotated[
    str,
    Field(min_length=8, max_length=128),
    AfterValidator(validate_password_strength),
]


class UserRegisterRequest(BaseModel):
    email: NormalizedEmail
    password: StrongPassword


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    is_active: bool


class ActivationRequest(BaseModel):
    token: str = Field(min_length=1, max_length=128)


class ResendActivationRequest(BaseModel):
    email: NormalizedEmail


class MessageResponse(BaseModel):
    message: str


class LoginRequest(BaseModel):
    email: NormalizedEmail
    password: str = Field(min_length=1, max_length=128)


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: StrongPassword


class PasswordResetRequest(BaseModel):
    email: NormalizedEmail


class PasswordResetCompleteRequest(BaseModel):
    token: str = Field(min_length=1, max_length=128)
    new_password: StrongPassword


class UserGroupUpdateRequest(BaseModel):
    group: UserGroupEnum


class UserGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str


class UserAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    is_active: bool
    created_at: datetime
    group: UserGroupResponse


class UserListResponse(BaseModel):
    items: list[UserAdminResponse]
    total: int
    page: int
    page_size: int
