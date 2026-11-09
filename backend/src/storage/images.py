from src.storage.exceptions import ImageTooLargeError, UnsupportedImageTypeError

IMAGE_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def validate_image(
    data: bytes, content_type: str | None, max_size: int
) -> tuple[str, str]:
    """Check type and size of an uploaded image;
    return content type and file extension."""
    if content_type not in IMAGE_EXTENSIONS:
        raise UnsupportedImageTypeError()
    if len(data) > max_size:
        raise ImageTooLargeError(max_size)
    return content_type, IMAGE_EXTENSIONS[content_type]
