from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

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
