# =============================================================================
# PH Agent Hub — Session Service (CRUD + tool activation)
# =============================================================================

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import NotFoundError, ValidationError
from ..db.orm.sessions import Session, SessionActiveTool
from ..db.orm.tools import Tool


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------


async def create_session(
    db: AsyncSession,
    tenant_id: str,
    user_id: str,
    title: str,
    is_temporary: bool = False,
    is_pinned: bool = False,
    selected_template_id: str | None = None,
    selected_prompt_id: str | None = None,
    selected_skill_id: str | None = None,
    selected_model_id: str | None = None,
) -> Session:
    """Create a new permanent session."""
    session = Session(
        tenant_id=tenant_id,
        user_id=user_id,
        title=title,
        is_temporary=is_temporary,
        is_pinned=is_pinned,
        selected_template_id=selected_template_id,
        selected_prompt_id=selected_prompt_id,
        selected_skill_id=selected_skill_id,
        selected_model_id=selected_model_id,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session_by_id(db: AsyncSession, session_id: str) -> Session | None:
    """Look up a session by primary key."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    return result.scalar_one_or_none()


async def list_sessions_for_user(
    db: AsyncSession,
    user_id: str,
    tenant_id: str,
) -> list[Session]:
    """Return all permanent sessions for a user in their tenant.

    Temporary sessions are excluded from the list.
    """
    stmt = (
        select(Session)
        .where(
            Session.user_id == user_id,
            Session.tenant_id == tenant_id,
            Session.is_temporary == False,  # noqa: E712
        )
        .order_by(Session.updated_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_session(
    db: AsyncSession,
    session_id: str,
    **fields,
) -> Session:
    """Update a session's fields. Raises NotFoundError if missing."""
    session = await get_session_by_id(db, session_id)
    if session is None:
        raise NotFoundError("Session not found")

    for key, value in fields.items():
        if hasattr(session, key):
            setattr(session, key, value)

    await db.commit()
    await db.refresh(session)
    return session


async def delete_session(db: AsyncSession, session_id: str) -> None:
    """Delete a session by ID.

    Clears FK references from messages and session_active_tools,
    then deletes the session. Raises NotFoundError if missing.
    """
    from sqlalchemy import delete as sa_delete
    from ..db.orm.messages import Message
    from ..db.orm.sessions import SessionActiveTool

    session = await get_session_by_id(db, session_id)
    if session is None:
        raise NotFoundError("Session not found")

    # Clear FK references before deleting the session.
    # 1. Null out parent_message_id self-references within this session
    from sqlalchemy import update as sa_update
    await db.execute(
        sa_update(Message)
        .where(Message.session_id == session_id)
        .values(parent_message_id=None)
    )
    await db.flush()

    # 2. Delete all messages in this session
    await db.execute(
        sa_delete(Message).where(Message.session_id == session_id)
    )
    # 3. Delete active tool associations
    await db.execute(
        sa_delete(SessionActiveTool).where(
            SessionActiveTool.session_id == session_id
        )
    )
    await db.flush()

    await db.delete(session)
    await db.commit()


# ---------------------------------------------------------------------------
# Session active tool management
# ---------------------------------------------------------------------------


async def get_session_tools(
    db: AsyncSession, session_id: str
) -> list[Tool]:
    """Return all active tools for a session (as Tool ORM objects)."""
    stmt = (
        select(Tool)
        .join(SessionActiveTool, SessionActiveTool.tool_id == Tool.id)
        .where(SessionActiveTool.session_id == session_id)
        .order_by(Tool.name)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _get_session_tool_ids(
    db: AsyncSession, session_id: str
) -> list[str]:
    """Return just the tool_id list for a session."""
    stmt = select(SessionActiveTool.tool_id).where(
        SessionActiveTool.session_id == session_id
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


async def add_session_tool(
    db: AsyncSession,
    session_id: str,
    tool_id: str,
    tenant_id: str,
) -> SessionActiveTool:
    """Activate a tool for a session.

    Validates that the tool exists, belongs to the same tenant, and is enabled.
    Raises NotFoundError if the session or tool is not found.
    Raises ValidationError if the tool is disabled or from a different tenant.
    """
    # Verify session exists
    session = await get_session_by_id(db, session_id)
    if session is None:
        raise NotFoundError("Session not found")

    # Verify tool exists, is enabled, and belongs to the tenant
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if tool is None:
        raise NotFoundError("Tool not found")
    if not tool.enabled:
        raise ValidationError("Tool is disabled")
    if tool.tenant_id != tenant_id:
        raise ValidationError("Tool does not belong to this tenant")

    # Check for duplicate
    existing = await db.execute(
        select(SessionActiveTool).where(
            SessionActiveTool.session_id == session_id,
            SessionActiveTool.tool_id == tool_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValidationError("Tool already active for this session")

    sat = SessionActiveTool(session_id=session_id, tool_id=tool_id)
    db.add(sat)
    await db.commit()
    await db.refresh(sat)
    return sat


async def remove_session_tool(
    db: AsyncSession,
    session_id: str,
    tool_id: str,
) -> None:
    """Deactivate a tool for a session.

    Raises NotFoundError if the association does not exist.
    """
    stmt = delete(SessionActiveTool).where(
        SessionActiveTool.session_id == session_id,
        SessionActiveTool.tool_id == tool_id,
    )
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise NotFoundError("Tool not active for this session")
    await db.commit()
