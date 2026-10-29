from src.accounts.security import (
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_hash_password_does_not_return_plain_password() -> None:
    assert hash_password("StrongPass1!") != "StrongPass1!"


def test_hash_password_uses_random_salt() -> None:
    assert hash_password("StrongPass1!") != hash_password("StrongPass1!")


def test_verify_password_accepts_correct_password() -> None:
    hashed = hash_password("StrongPass1!")

    assert verify_password("StrongPass1!", hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("StrongPass1!")

    assert verify_password("WrongPass1!", hashed) is False


def test_generate_token_returns_unique_tokens() -> None:
    assert generate_token() != generate_token()


def test_hash_token_is_deterministic() -> None:
    token = generate_token()

    assert hash_token(token) == hash_token(token)


def test_hash_token_returns_sha256_hex_digest() -> None:
    token_hash = hash_token(generate_token())

    assert len(token_hash) == 64
    assert all(char in "0123456789abcdef" for char in token_hash)
