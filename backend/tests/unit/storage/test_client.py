from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from src.config.settings import get_settings
from src.storage import client as storage


@pytest.fixture
def s3_client_mock(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock()
    monkeypatch.setattr(storage, "s3_client", mock)
    return mock


def test_upload_file_sets_content_type(s3_client_mock: MagicMock) -> None:
    storage.upload_file("avatars/1/a.png", b"data", "image/png")

    s3_client_mock.put_object.assert_called_once_with(
        Bucket=get_settings().S3_BUCKET_NAME,
        Key="avatars/1/a.png",
        Body=b"data",
        ContentType="image/png",
    )


def test_delete_file_deletes_object(s3_client_mock: MagicMock) -> None:
    storage.delete_file("avatars/1/a.png")

    s3_client_mock.delete_object.assert_called_once_with(
        Bucket=get_settings().S3_BUCKET_NAME, Key="avatars/1/a.png"
    )


def test_get_file_url_is_signed_for_public_endpoint() -> None:
    # Signing is local (no network), so the real public client is used.
    settings = get_settings()

    url = storage.get_file_url("avatars/1/a.png")

    assert url.startswith(
        f"{settings.S3_PUBLIC_ENDPOINT_URL}/{settings.S3_BUCKET_NAME}/avatars/1/a.png"
    )
    assert "X-Amz-Signature=" in url
    assert f"X-Amz-Expires={storage.FILE_URL_EXPIRES_SECONDS}" in url


def test_ensure_bucket_exists_skips_existing_bucket(
    s3_client_mock: MagicMock,
) -> None:
    storage.ensure_bucket_exists()

    s3_client_mock.create_bucket.assert_not_called()


def test_ensure_bucket_exists_creates_missing_bucket(
    s3_client_mock: MagicMock,
) -> None:
    s3_client_mock.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "404"}}, "HeadBucket"
    )

    storage.ensure_bucket_exists()

    s3_client_mock.create_bucket.assert_called_once_with(
        Bucket=get_settings().S3_BUCKET_NAME
    )
