# =============================================================================
# PH Agent Hub — Upload Service
# =============================================================================
# File-upload lifecycle (MinIO + ``file_uploads`` table).
# Only ``storage/s3.py`` calls ``boto3`` (single-module rule).
# =============================================================================

import tempfile
import os
import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.exceptions import ForbiddenError, NotFoundError, ValidationError
from ..db.orm.file_uploads import FileUpload
from ..db.orm.users import User
from ..storage import s3

# Document MIME types that can have text extracted
_EXTRACTABLE_MIME_TYPES = frozenset({
    "application/pdf",
    "text/csv",
    "text/plain",
    "text/markdown",
    "application/json",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
})

# Image MIME types (no text extraction)
_IMAGE_MIME_TYPES = frozenset({
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
})


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

    # 5a. Extract text for document types via markitdown
    extracted_text: str | None = None
    if content_type in _EXTRACTABLE_MIME_TYPES:
        try:
            extracted_text = await _extract_text(
                file_bytes=file_bytes,
                filename=original_filename,
                content_type=content_type,
            )
        except Exception:
            # Best-effort: extraction failure should not block upload
            pass

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
        extracted_text=extracted_text,
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


async def delete_uploads_for_session(
    db: AsyncSession,
    session_id: str,
) -> None:
    """Delete all file uploads (MinIO objects + DB rows) for a session.

    Used as cascade cleanup before deleting a session.
    Does NOT commit — the caller is responsible for committing.
    """
    result = await db.execute(
        select(FileUpload).where(FileUpload.session_id == session_id)
    )
    uploads = list(result.scalars().all())

    for upload in uploads:
        try:
            await s3.delete_object(bucket=upload.bucket, key=upload.storage_key)
        except Exception:
            pass  # Best-effort: MinIO object may already be gone

    if uploads:
        await db.execute(
            delete(FileUpload).where(FileUpload.session_id == session_id)
        )
        await db.flush()


async def delete_uploads_for_message(
    db: AsyncSession,
    message_id: str,
) -> None:
    """Delete all file uploads (MinIO objects + DB rows) linked to a message.

    Used as cascade cleanup before deleting a message.
    Does NOT commit — the caller is responsible for committing.
    """
    result = await db.execute(
        select(FileUpload).where(FileUpload.message_id == message_id)
    )
    uploads = list(result.scalars().all())

    for upload in uploads:
        try:
            await s3.delete_object(bucket=upload.bucket, key=upload.storage_key)
        except Exception:
            pass  # Best-effort

    if uploads:
        await db.execute(
            delete(FileUpload).where(FileUpload.message_id == message_id)
        )
        await db.flush()


async def list_uploads_for_message(
    db: AsyncSession,
    message_id: str,
) -> list[FileUpload]:
    """List all file uploads linked to a specific message."""
    result = await db.execute(
        select(FileUpload)
        .where(FileUpload.message_id == message_id)
        .order_by(FileUpload.created_at.asc())
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Text extraction (markitdown)
# ---------------------------------------------------------------------------


async def _extract_text(
    file_bytes: bytes,
    filename: str,
    content_type: str,
) -> str:
    """Extract text from a document using markitdown.

    Writes bytes to a temp file so markitdown can use the filename
    extension to pick the correct converter.
    """
    import asyncio

    suffix = _get_suffix(filename)

    def _sync_extract() -> str:
        from markitdown import MarkItDown

        md = MarkItDown()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            result = md.convert(tmp_path)
            return result.text_content
        finally:
            os.unlink(tmp_path)

    return await asyncio.to_thread(_sync_extract)


def _get_suffix(filename: str) -> str:
    """Return a safe file suffix for temp file creation."""
    _, ext = os.path.splitext(filename)
    if ext and len(ext) <= 10:
        return ext
    return ""
