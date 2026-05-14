# =============================================================================
# PH Agent Hub — File List Tool (Built-in)
# =============================================================================
# Always-available discovery tool that lets the agent inspect uploaded files.
# Not stored in the DB — unconditionally appended in _resolve_tool_callables().
# =============================================================================

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from agent_framework import tool

logger = logging.getLogger(__name__)

MAX_FILE_CONTENT_CHARS = 50_000


def build_file_list_tool(
    db: AsyncSession,
    session_id: str,
    tenant_id: str,
    is_temporary: bool = False,
    uploaded_file_ids: list[str] | None = None,
) -> list:
    """Return built-in MAF @tools for file discovery and content reading.

    Args:
        db: Active async DB session.
        session_id: Current session ID.
        tenant_id: Current tenant ID.
        is_temporary: Whether the session is temporary (changes DB query).
        uploaded_file_ids: Specific file IDs for temp sessions (from Redis).
    """
    from ..db.orm.file_uploads import FileUpload

    @tool
    async def list_uploaded_files() -> list[dict[str, Any]]:
        """List all files uploaded in this conversation session.

        Returns filename, content type, size (KB), a short text preview,
        and the file_id.  To read the full extracted text of a file, use
        ``read_file_content(file_id)`` with the file_id returned here.
        Call this when a user mentions a file and you need its exact name
        (e.g. for the ERPNext ``upload_file`` tool).
        """
        if is_temporary and uploaded_file_ids:
            result = await db.execute(
                select(FileUpload).where(
                    FileUpload.id.in_(uploaded_file_ids),
                    FileUpload.tenant_id == tenant_id,
                )
            )
        elif is_temporary:
            # No file IDs tracked — return empty
            result = await db.execute(
                select(FileUpload).where(
                    FileUpload.id.in_([]),
                )
            )
        else:
            result = await db.execute(
                select(FileUpload).where(
                    FileUpload.session_id == session_id,
                    FileUpload.tenant_id == tenant_id,
                )
            )
        uploads = result.scalars().all()

        files: list[dict[str, Any]] = []
        for u in uploads:
            kb_size = u.size_bytes / 1024
            preview = ""
            if u.extracted_text:
                preview = u.extracted_text[:200]
                if len(u.extracted_text) > 200:
                    preview += "..."
            files.append({
                "file_id": u.id,
                "filename": u.original_filename,
                "content_type": u.content_type,
                "size_kb": round(kb_size, 1),
                "preview": preview,
            })

        logger.debug(
            "list_uploaded_files session=%s → %d files", session_id, len(files)
        )
        return files

    @tool
    async def read_file_content(file_id: str) -> dict[str, Any]:
        """Return the full extracted text content of a previously uploaded file.

        Args:
            file_id: The file ID returned by ``list_uploaded_files()``.

        Returns a dict with ``filename``, ``content_type``, ``text`` (the full
        extracted content), and ``truncated`` (bool, True if the text was
        truncated to {max_chars} characters).

        If the file is not found or has no extracted text, an error message
        is returned in the ``error`` field.
        """.format(max_chars=MAX_FILE_CONTENT_CHARS)
        try:
            UUID(file_id)  # validate format only
        except ValueError:
            return {"error": f"Invalid file_id: {file_id!r}"}

        result = await db.execute(
            select(FileUpload).where(
                FileUpload.id == file_id,
                FileUpload.tenant_id == tenant_id,
            )
        )
        upload = result.scalar_one_or_none()

        if upload is None:
            return {"error": f"File not found: {file_id}"}

        if not upload.extracted_text:
            return {
                "filename": upload.original_filename,
                "content_type": upload.content_type,
                "text": "",
                "truncated": False,
                "note": "No text could be extracted from this file.",
            }

        text = upload.extracted_text
        truncated = len(text) > MAX_FILE_CONTENT_CHARS
        if truncated:
            text = text[:MAX_FILE_CONTENT_CHARS]

        logger.debug(
            "read_file_content file_id=%s → %d chars (truncated=%s)",
            file_id, len(text), truncated,
        )
        return {
            "file_id": upload.id,
            "filename": upload.original_filename,
            "content_type": upload.content_type,
            "text": text,
            "truncated": truncated,
        }

    return [list_uploaded_files, read_file_content]
