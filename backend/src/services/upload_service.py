# =============================================================================
# PH Agent Hub — Upload Service
# =============================================================================
# File-upload lifecycle (MinIO + ``file_uploads`` table).
# Only ``storage/s3.py`` calls ``boto3`` (single-module rule).
# =============================================================================

import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.exceptions import ForbiddenError, NotFoundError, ValidationError
from ..db.orm.file_uploads import FileUpload
from ..db.orm.users import User
from ..storage import s3


async def create_upload(
    db: AsyncSession,
    session_data: dict,
    current_user: User,
    file_bytes: bytes,
    original_filename: str,
    content_type: str,
) -> FileUpload:
    """Upload a file to MinIO and create a ``FileUpload`` DB row.

    Raises:
        ValidationError: content_type not allowed or file too large.
        ForbiddenError: session is temporary.
    """
    # 1. Validate content type
    allowed_types = [
        t.strip() for t in settings.UPLOAD_ALLOWED_TYPES.split(",") if t.strip()
    ]
    if content_type not in allowed_types:
        raise ValidationError(
            f"File type '{content_type}' is not allowed. "
            f"Allowed types: {settings.UPLOAD_ALLOWED_TYPES}"
        )

    # 2. Validate size
    if len(file_bytes) > settings.UPLOAD_MAX_SIZE_BYTES:
        raise ValidationError(
            f"File size {len(file_bytes)} exceeds maximum "
            f"{settings.UPLOAD_MAX_SIZE_BYTES} bytes"
        )

    # 3. Reject temporary sessions
    if session_data.get("is_temporary", False):
        raise ForbiddenError("Uploads are disabled for temporary sessions")

    # 4. Build storage path
    file_id = str(uuid.uuid4())
    bucket = f"{settings.MINIO_BUCKET_PREFIX}-{current_user.tenant_id}"
    key = (
        f"uploads/{current_user.id}/{session_data['id']}/"
        f"{file_id}-{original_filename}"
    )

    # 5. Upload to MinIO
    await s3.ensure_bucket_exists(bucket)
    await s3.upload_object(bucket, key, file_bytes, content_type)

    # 6. Persist DB row
    upload = FileUpload(
        id=file_id,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        session_id=session_data["id"],
        original_filename=original_filename,
        content_type=content_type,
        size_bytes=len(file_bytes),
        storage_key=key,
        bucket=bucket,
        is_temporary=False,
    )
    db.add(upload)
    await db.commit()
    await db.refresh(upload)
    return upload


async def list_uploads(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> list[FileUpload]:
    """List all file uploads for a session owned by a user."""
    result = await db.execute(
        select(FileUpload)
        .where(
            FileUpload.session_id == session_id,
            FileUpload.user_id == user_id,
        )
        .order_by(FileUpload.created_at.desc())
    )
    return list(result.scalars().all())


async def get_upload_by_id(
    db: AsyncSession,
    file_id: str,
    user_id: str,
) -> FileUpload:
    """Get a single upload by ID.  Raises if not found or wrong owner."""
    result = await db.execute(
        select(FileUpload).where(FileUpload.id == file_id)
    )
    upload = result.scalar_one_or_none()

    if upload is None:
        raise NotFoundError("File upload not found")
    if upload.user_id != user_id:
        raise ForbiddenError("You do not own this file upload")
    return upload


async def generate_presigned_url(
    db: AsyncSession,
    file_id: str,
    user_id: str,
    expires_in: int = 900,
) -> str:
    """Generate a presigned download URL for an uploaded file."""
    upload = await get_upload_by_id(db, file_id, user_id)
    return await s3.generate_presigned_url(
        bucket=upload.bucket,
        key=upload.storage_key,
        expires_in=expires_in,
    )


async def delete_upload(
    db: AsyncSession,
    file_id: str,
    user_id: str,
) -> None:
    """Delete a file upload (MinIO object + DB row)."""
    upload = await get_upload_by_id(db, file_id, user_id)

    await s3.delete_object(bucket=upload.bucket, key=upload.storage_key)
    await db.execute(delete(FileUpload).where(FileUpload.id == file_id))
    await db.commit()


async def link_uploads_to_message(
    db: AsyncSession,
    file_ids: list[str],
    message_id: str,
    user_id: str,
) -> None:
    """Link pre-uploaded files to an assistant message.

    Only links rows owned by *user_id* and currently with
    ``message_id IS NULL``.
    """
    if not file_ids:
        return

    await db.execute(
        update(FileUpload)
        .where(
            FileUpload.id.in_(file_ids),
            FileUpload.user_id == user_id,
            FileUpload.message_id.is_(None),
        )
        .values(message_id=message_id)
    )
    await db.commit()
