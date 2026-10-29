import pytest

from src.accounts.validators import validate_password_strength


def test_validate_password_strength_returns_valid_password() -> None:
    password = "StrongPass1!"

    assert validate_password_strength(password) == password


@pytest.mark.parametrize(
    ("password", "message"),
    [
        ("weakpass1!", "uppercase"),
        ("WEAKPASS1!", "lowercase"),
        ("WeakPass!!", "digit"),
        ("WeakPass11", "special character"),
    ],
)
def test_validate_password_strength_rejects_weak_password(
    password: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_password_strength(password)
