import pytest

from src.storage.exceptions import ImageTooLargeError, UnsupportedImageTypeError
from src.storage.images import validate_image

MAX_SIZE = 100


@pytest.mark.parametrize(
    ("content_type", "extension"),
    [("image/jpeg", "jpg"), ("image/png", "png"), ("image/webp", "webp")],
)
def test_validate_image_returns_type_and_extension(
    content_type: str, extension: str
) -> None:
    assert validate_image(b"data", content_type, MAX_SIZE) == (
        content_type,
        extension,
    )


@pytest.mark.parametrize(
    "content_type", [None, "", "image/gif", "image/svg+xml", "text/plain"]
)
def test_validate_image_rejects_unsupported_type(content_type: str | None) -> None:
    with pytest.raises(UnsupportedImageTypeError):
        validate_image(b"data", content_type, MAX_SIZE)


def test_validate_image_accepts_max_size() -> None:
    validate_image(b"x" * MAX_SIZE, "image/png", MAX_SIZE)


def test_validate_image_rejects_too_large() -> None:
    with pytest.raises(ImageTooLargeError):
        validate_image(b"x" * (MAX_SIZE + 1), "image/png", MAX_SIZE)


def test_validate_image_checks_type_before_size() -> None:
    with pytest.raises(UnsupportedImageTypeError):
        validate_image(b"x" * (MAX_SIZE + 1), "image/gif", MAX_SIZE)


def test_image_too_large_error_message_in_megabytes() -> None:
    error = ImageTooLargeError(5 * 1024 * 1024)

    assert str(error) == "Image must not exceed 5 MB"
    assert error.max_size == 5 * 1024 * 1024
