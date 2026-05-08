# =============================================================================
# PH Agent Hub — MinIO / S3 Client (Singleton)
# =============================================================================
# Single-module rule: ONLY this file calls `boto3`.
# All storage operations go through the helpers below.
#
# A3 resolution: boto3 is synchronous; we wrap every call in
# `asyncio.to_thread()` (Python 3.9+) to avoid blocking the event loop.
# =============================================================================

import asyncio
from functools import lru_cache

import boto3
from botocore.client import Config

from ..core.config import settings


@lru_cache()
def get_client():
    """Return a singleton boto3 S3 client configured for MinIO."""
    return boto3.client(
        "s3",
        endpoint_url=settings.MINIO_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
    )


async def upload_object(bucket: str, key: str, data: bytes, content_type: str) -> None:
    """Upload an object to MinIO."""
    client = get_client()

    def _upload():
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    await asyncio.to_thread(_upload)


async def delete_object(bucket: str, key: str) -> None:
    """Delete an object from MinIO."""
    client = get_client()

    def _delete():
        client.delete_object(Bucket=bucket, Key=key)

    await asyncio.to_thread(_delete)


async def generate_presigned_url(
    bucket: str, key: str, expires_in: int = 900
) -> str:
    """Generate a presigned URL for downloading an object (default 15 min TTL).

    If ``MINIO_PUBLIC_ENDPOINT`` is set, a separate boto3 client
    configured with the public endpoint is used so the signature
    matches the ``Host`` header the browser sends.
    """
    public = settings.MINIO_PUBLIC_ENDPOINT
    internal = settings.MINIO_ENDPOINT

    if public and public != internal:
        # Use a client configured with the public endpoint for correct signing
        public_client = boto3.client(
            "s3",
            endpoint_url=public,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
        )

        def _generate():
            return public_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_in,
            )

        return await asyncio.to_thread(_generate)

    # No public endpoint — sign for MinIO's internal address directly
    client = get_client()

    def _generate():
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    return await asyncio.to_thread(_generate)


async def ensure_bucket_exists(bucket: str) -> None:
    """Create the bucket if it doesn't already exist."""
    client = get_client()

    def _ensure():
        try:
            client.head_bucket(Bucket=bucket)
        except Exception:
            client.create_bucket(Bucket=bucket)

    await asyncio.to_thread(_ensure)
