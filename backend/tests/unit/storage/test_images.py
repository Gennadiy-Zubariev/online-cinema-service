import struct
import zlib

import pytest

from src.storage.exceptions import ImageTooLargeError, UnsupportedImageTypeError
from src.storage.images import validate_image
from tests.images import make_image

MAX_SIZE = 1000


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + data)
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)


def png_header_only(width: int, height: int) -> bytes:
    """A PNG that declares a size but has no pixel data (a decompression bomb)."""
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", header) + png_chunk(b"IEND", b"")


@pytest.mark.parametrize(
    ("image_format", "expected"),
    [
        ("JPEG", ("image/jpeg", "jpg")),
        ("PNG", ("image/png", "png")),
        ("WEBP", ("image/webp", "webp")),
    ],
)
def test_validate_image_detects_format_from_bytes(
    image_format: str, expected: tuple[str, str]
) -> None:
    assert validate_image(make_image(image_format), MAX_SIZE) == expected


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(make_image("GIF"), id="gif"),
        pytest.param(make_image("BMP"), id="bmp"),
        pytest.param(b'<svg xmlns="http://www.w3.org/2000/svg"/>', id="svg"),
        pytest.param(b"<html><script>alert(1)</script></html>", id="html"),
        pytest.param(b"not an image", id="text"),
        pytest.param(b"", id="empty"),
    ],
)
def test_validate_image_rejects_non_supported_content(data: bytes) -> None:
    with pytest.raises(UnsupportedImageTypeError):
        validate_image(data, MAX_SIZE)


def test_validate_image_rejects_truncated_png() -> None:
    # Valid header, broken body: verify() must catch it, not only the header.
    with pytest.raises(UnsupportedImageTypeError):
        validate_image(make_image("PNG")[:-20], MAX_SIZE)


def test_validate_image_rejects_png_with_corrupted_data() -> None:
    data = bytearray(make_image("PNG"))
    data[30] ^= 0xFF  # inside the IHDR chunk -> CRC mismatch

    with pytest.raises(UnsupportedImageTypeError):
        validate_image(bytes(data), MAX_SIZE)


def test_validate_image_rejects_decompression_bomb() -> None:
    # Tiny file, 100000 x 100000 pixels declared: Pillow refuses to open it.
    with pytest.raises(UnsupportedImageTypeError):
        validate_image(png_header_only(100_000, 100_000), MAX_SIZE)


def test_validate_image_accepts_max_size() -> None:
    assert validate_image(make_image("PNG", size=MAX_SIZE), MAX_SIZE) == (
        "image/png",
        "png",
    )


def test_validate_image_rejects_too_large() -> None:
    with pytest.raises(ImageTooLargeError):
        validate_image(make_image("PNG", size=MAX_SIZE + 1), MAX_SIZE)


def test_validate_image_checks_size_before_content() -> None:
    # Oversized files are rejected without being parsed.
    with pytest.raises(ImageTooLargeError):
        validate_image(b"x" * (MAX_SIZE + 1), MAX_SIZE)


def test_image_too_large_error_message_in_megabytes() -> None:
    error = ImageTooLargeError(5 * 1024 * 1024)

    assert str(error) == "Image must not exceed 5 MB"
    assert error.max_size == 5 * 1024 * 1024
