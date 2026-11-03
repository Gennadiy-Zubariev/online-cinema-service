import pytest
from pydantic import ValidationError

from src.accounts.models import User
from src.accounts.schemas import LoginRequest, UserRegisterRequest, UserResponse

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


def test_login_request_lowercases_email() -> None:
    data = LoginRequest(email="User@Example.COM", password=VALID_PASSWORD)

    assert data.email == "user@example.com"


def test_login_request_does_not_check_password_strength() -> None:
    # Strength is enforced only where a password is set, not at login.
    data = LoginRequest(email="user@example.com", password="weak")

    assert data.password == "weak"
