import pytest
from pydantic import ValidationError

from src.accounts.models import User
from src.accounts.schemas import UserRegisterRequest, UserResponse

VALID_PASSWORD = "StrongPass1!"


def test_user_register_request_lowercases_email() -> None:
    data = UserRegisterRequest(email="John.Doe@Example.COM", password=VALID_PASSWORD)

    assert data.email == "john.doe@example.com"


def test_user_register_request_rejects_invalid_email() -> None:
    with pytest.raises(ValidationError):
        UserRegisterRequest(email="not-an-email", password=VALID_PASSWORD)


@pytest.mark.parametrize(
    "password",
    ["Sh0rt!", "Long1!" + "a" * 123],
    ids=["too_short", "too_long"],
)
def test_user_register_request_rejects_password_with_invalid_length(
    password: str,
) -> None:
    with pytest.raises(ValidationError):
        UserRegisterRequest(email="user@example.com", password=password)


def test_user_register_request_rejects_weak_password() -> None:
    with pytest.raises(ValidationError, match="uppercase"):
        UserRegisterRequest(email="user@example.com", password="weakpass1!")


def test_user_response_is_built_from_model_without_password() -> None:
    user = User(id=1, email="user@example.com", hashed_password="hash", is_active=False)

    response = UserResponse.model_validate(user)

    assert response.model_dump() == {
        "id": 1,
        "email": "user@example.com",
        "is_active": False,
    }
