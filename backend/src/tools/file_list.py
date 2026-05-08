# =============================================================================
# PH Agent Hub — File List Tool (Built-in)
# =============================================================================
# Always-available discovery tool that lets the agent inspect uploaded files.
# Not stored in the DB — unconditionally appended in _resolve_tool_callables().
# =============================================================================

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from agent_framework import tool

logger = logging.getLogger(__name__)


def build_file_list_tool(
    db: AsyncSession,
    session_id: str,
    tenant_id: str,
) -> list:
    """Return a single MAF @tool that lists file uploads for the session.

    Args:
        db: Active async DB session.
        session_id: Current session ID.
        tenant_id: Current tenant ID.
    """
    from ..db.orm.file_uploads import FileUpload

    @tool
    async def list_uploaded_files() -> list[dict[str, Any]]:
        """List all files uploaded in this conversation session.

        Returns filename, content type, size (KB), a short text preview,
        and the file_id needed to reference it in other tools.  Call this
        when a user mentions a file and you need to know its exact name
        (e.g. for the ERPNext ``upload_file`` tool).
        """
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

    return [list_uploaded_files]
