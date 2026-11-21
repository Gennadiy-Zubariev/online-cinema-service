from typing import TYPE_CHECKING

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from src.config.settings import Settings, get_settings

if TYPE_CHECKING:
    # Type stubs are a dev dependency: not installed in the production image.
    from mypy_boto3_s3 import S3Client

settings = get_settings()


def _create_client(endpoint_url: str, settings: Settings) -> "S3Client":
    """Create an S3 client for the endpoint with SigV4 signing.

    Without signature_version and region boto3 falls back to SigV2,
    which AWS S3 rejects.
    """
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=settings.S3_REGION,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY.get_secret_value(),
        config=Config(signature_version="s3v4"),
    )


s3_client = _create_client(settings.S3_ENDPOINT_URL, settings)
# Signs URLs for the browser; makes no network calls.
s3_public_client = _create_client(settings.S3_PUBLIC_ENDPOINT_URL, settings)


def ensure_bucket_exists() -> None:
    """Create the bucket if it does not exist (called on app startup)."""
    try:
        s3_client.head_bucket(Bucket=settings.S3_BUCKET_NAME)
    except ClientError:
        s3_client.create_bucket(Bucket=settings.S3_BUCKET_NAME)


FILE_URL_EXPIRES_SECONDS = 3600


def upload_file(key: str, data: bytes, content_type: str) -> None:
    """Upload bytes under the key; ContentType is required for browsers.

    Sync network call: use run_in_threadpool in async code.
    """
    s3_client.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def delete_file(key: str) -> None:
    """Delete the object; idempotent (a missing key is not an error).

    Sync network call: use run_in_threadpool in async code.
    """
    s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)


def get_file_url(key: str) -> str:
    """Return a presigned GET URL valid for FILE_URL_EXPIRES_SECONDS.

    Signed with the public endpoint so the browser can open it; no network call.
    """
    return s3_public_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": key},
        ExpiresIn=FILE_URL_EXPIRES_SECONDS,
    )
