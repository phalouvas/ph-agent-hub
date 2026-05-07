# =============================================================================
# PH Agent Hub — Chat API Router
# =============================================================================
# Session CRUD (permanent via MariaDB + temporary via Redis), message
# sending (agent run), and session-level tool activation.
# =============================================================================

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..agents.runner import run_agent
from ..core.dependencies import get_current_user, get_db
from ..core.exceptions import (
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from ..core.redis import (
    append_temp_message,
    delete_temp_session,
    get_temp_messages,
    get_temp_session,
    store_temp_session,
)
from ..db.orm.messages import Message
from ..db.orm.sessions import Session
from ..db.orm.tools import Tool
from ..db.orm.users import User as UserORM
from ..services import session_service

router = APIRouter(prefix="/chat", tags=["chat"])

# =============================================================================
# Pydantic Schemas
# =============================================================================


class SessionCreate(BaseModel):
    title: str = "New Chat"
    is_temporary: bool = False
    is_pinned: bool = False
    selected_template_id: str | None = None
    selected_prompt_id: str | None = None
    selected_skill_id: str | None = None
    selected_model_id: str | None = None
    active_tool_ids: list[str] | None = None


class SessionUpdate(BaseModel):
    title: str | None = None
    is_pinned: bool | None = None
    selected_template_id: str | None = None
    selected_prompt_id: str | None = None
    selected_skill_id: str | None = None
    selected_model_id: str | None = None


class SessionResponse(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    title: str
    is_temporary: bool
    is_pinned: bool
    selected_template_id: str | None
    selected_prompt_id: str | None
    selected_skill_id: str | None
    selected_model_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: str
    session_id: str
    parent_message_id: str | None
    branch_index: int
    sender: str
    content: list | None
    model_id: str | None
    tool_calls: list | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SendMessageResponse(BaseModel):
    message_id: str
    content: str
    model_id: str | None


class ToolResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    type: str
    config: dict | None
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# =============================================================================
# Internal helpers
# =============================================================================


def _session_to_dict(session: Session) -> dict[str, Any]:
    """Convert a Session ORM object to a plain dict for runner consumption."""
    return {
        "id": session.id,
        "tenant_id": session.tenant_id,
        "user_id": session.user_id,
        "title": session.title,
        "is_temporary": session.is_temporary,
        "is_pinned": session.is_pinned,
        "selected_template_id": session.selected_template_id,
        "selected_prompt_id": session.selected_prompt_id,
        "selected_skill_id": session.selected_skill_id,
        "selected_model_id": session.selected_model_id,
    }


async def _load_session(
    db: AsyncSession, session_id: str
) -> dict[str, Any]:
    """Load a session from MariaDB or Redis, returning a unified dict.

    Raises NotFoundError if neither source has the session.
    """
    # Try DB first
    session = await session_service.get_session_by_id(db, session_id)
    if session is not None:
        return _session_to_dict(session)

    # Try Redis
    temp = await get_temp_session(session_id)
    if temp is not None:
        return temp

    raise NotFoundError("Session not found")


async def _require_session_owner(
    session_data: dict,
    current_user: UserORM,
) -> None:
    """Raise ForbiddenError if the session doesn't belong to the current user."""
    if session_data.get("user_id") != current_user.id:
        raise ForbiddenError("You do not own this session")
    if session_data.get("tenant_id") != current_user.tenant_id:
        raise ForbiddenError("Session belongs to a different tenant")


# =============================================================================
# Session CRUD
# =============================================================================


@router.post("/session", response_model=SessionResponse, status_code=201)
async def create_session(
    body: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """Create a permanent (DB) or temporary (Redis) session."""
    if body.is_temporary:
        # Create in Redis
        session_id = str(uuid.uuid4())
        data: dict[str, Any] = {
            "id": session_id,
            "tenant_id": current_user.tenant_id,
            "user_id": current_user.id,
            "title": body.title,
            "is_temporary": True,
            "is_pinned": body.is_pinned,
            "selected_template_id": body.selected_template_id,
            "selected_prompt_id": body.selected_prompt_id,
            "selected_skill_id": body.selected_skill_id,
            "selected_model_id": body.selected_model_id,
            "active_tool_ids": body.active_tool_ids or [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        await store_temp_session(session_id, data)

        # Return a SessionResponse-compatible dict
        return {
            "id": session_id,
            "tenant_id": current_user.tenant_id,
            "user_id": current_user.id,
            "title": body.title,
            "is_temporary": True,
            "is_pinned": body.is_pinned,
            "selected_template_id": body.selected_template_id,
            "selected_prompt_id": body.selected_prompt_id,
            "selected_skill_id": body.selected_skill_id,
            "selected_model_id": body.selected_model_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    else:
        # Create in MariaDB
        session = await session_service.create_session(
            db=db,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            title=body.title,
            is_temporary=False,
            is_pinned=body.is_pinned,
            selected_template_id=body.selected_template_id,
            selected_prompt_id=body.selected_prompt_id,
            selected_skill_id=body.selected_skill_id,
            selected_model_id=body.selected_model_id,
        )
        return SessionResponse.model_validate(session)


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """List the current user's permanent sessions (temp sessions excluded)."""
    sessions = await session_service.list_sessions_for_user(
        db=db,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    return [SessionResponse.model_validate(s) for s in sessions]


@router.get("/session/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """Get a session by ID (from DB or Redis)."""
    data = await _load_session(db, session_id)
    await _require_session_owner(data, current_user)

    return {
        "id": data["id"],
        "tenant_id": data["tenant_id"],
        "user_id": data["user_id"],
        "title": data["title"],
        "is_temporary": data.get("is_temporary", False),
        "is_pinned": data.get("is_pinned", False),
        "selected_template_id": data.get("selected_template_id"),
        "selected_prompt_id": data.get("selected_prompt_id"),
        "selected_skill_id": data.get("selected_skill_id"),
        "selected_model_id": data.get("selected_model_id"),
        "created_at": _parse_datetime(data.get("created_at")),
        "updated_at": _parse_datetime(data.get("updated_at")),
    }


@router.put("/session/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    body: SessionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """Update a session's fields (DB or Redis)."""
    data = await _load_session(db, session_id)
    await _require_session_owner(data, current_user)

    is_temp = data.get("is_temporary", False)

    if is_temp:
        # Update Redis blob
        update_fields = body.model_dump(exclude_unset=True)
        data.update(update_fields)
        data["updated_at"] = datetime.utcnow().isoformat()
        await store_temp_session(session_id, data)

        return {
            "id": data["id"],
            "tenant_id": data["tenant_id"],
            "user_id": data["user_id"],
            "title": data["title"],
            "is_temporary": True,
            "is_pinned": data.get("is_pinned", False),
            "selected_template_id": data.get("selected_template_id"),
            "selected_prompt_id": data.get("selected_prompt_id"),
            "selected_skill_id": data.get("selected_skill_id"),
            "selected_model_id": data.get("selected_model_id"),
            "created_at": _parse_datetime(data.get("created_at")),
            "updated_at": datetime.utcnow(),
        }
    else:
        session = await session_service.update_session(
            db=db,
            session_id=session_id,
            **body.model_dump(exclude_unset=True),
        )
        return SessionResponse.model_validate(session)


@router.delete("/session/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """Delete a session (DB or Redis)."""
    data = await _load_session(db, session_id)
    await _require_session_owner(data, current_user)

    is_temp = data.get("is_temporary", False)

    if is_temp:
        await delete_temp_session(session_id)
    else:
        await session_service.delete_session(db, session_id)


# =============================================================================
# Messages
# =============================================================================


@router.get(
    "/session/{session_id}/messages",
    response_model=list[MessageResponse],
)
async def list_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """List messages for a session (DB or Redis)."""
    data = await _load_session(db, session_id)
    await _require_session_owner(data, current_user)

    is_temp = data.get("is_temporary", False)

    if is_temp:
        msgs = await get_temp_messages(session_id)
        return [
            MessageResponse(
                id=m.get("id", ""),
                session_id=session_id,
                parent_message_id=m.get("parent_message_id"),
                branch_index=m.get("branch_index", 0),
                sender=m.get("sender", "user"),
                content=m.get("content"),
                model_id=m.get("model_id"),
                tool_calls=m.get("tool_calls"),
                is_deleted=m.get("is_deleted", False),
                created_at=_parse_datetime(m.get("created_at")),
                updated_at=_parse_datetime(m.get("updated_at")),
            )
            for m in msgs
        ]
    else:
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()
        return [MessageResponse.model_validate(m) for m in messages]


@router.post(
    "/session/{session_id}/message",
    response_model=SendMessageResponse,
)
async def send_message(
    session_id: str,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """Send a user message and run the agent. Returns the assistant's response."""
    data = await _load_session(db, session_id)
    await _require_session_owner(data, current_user)

    # Run the agent
    response_text = await run_agent(
        session_data=data,
        user_message=body.content,
        db=db,
        current_user=current_user,
    )

    # Get the most recent assistant message ID for the response
    message_id = str(uuid.uuid4())
    model_id = data.get("selected_model_id")

    return SendMessageResponse(
        message_id=message_id,
        content=response_text,
        model_id=model_id,
    )


# =============================================================================
# Session Tools
# =============================================================================


@router.get(
    "/session/{session_id}/tools",
    response_model=list[ToolResponse],
)
async def list_session_tools(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """List active tools for a session (DB or Redis)."""
    data = await _load_session(db, session_id)
    await _require_session_owner(data, current_user)

    is_temp = data.get("is_temporary", False)

    if is_temp:
        tool_ids = data.get("active_tool_ids", [])
        if not tool_ids:
            return []
        result = await db.execute(
            select(Tool).where(
                Tool.id.in_(tool_ids),
                Tool.tenant_id == current_user.tenant_id,
            )
        )
        tools = result.scalars().all()
        return [ToolResponse.model_validate(t) for t in tools]
    else:
        tools = await session_service.get_session_tools(db, session_id)
        return [ToolResponse.model_validate(t) for t in tools]


@router.post(
    "/session/{session_id}/tools/{tool_id}",
    status_code=204,
)
async def add_session_tool(
    session_id: str,
    tool_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """Activate a tool for a session (DB or Redis)."""
    data = await _load_session(db, session_id)
    await _require_session_owner(data, current_user)

    # Validate tool exists and is enabled
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if tool is None:
        raise NotFoundError("Tool not found")
    if not tool.enabled:
        raise ValidationError("Tool is disabled")
    if tool.tenant_id != current_user.tenant_id:
        raise ValidationError("Tool does not belong to this tenant")

    is_temp = data.get("is_temporary", False)

    if is_temp:
        tool_ids: list[str] = list(data.get("active_tool_ids", []))
        if tool_id not in tool_ids:
            tool_ids.append(tool_id)
            data["active_tool_ids"] = tool_ids
            await store_temp_session(session_id, data)
    else:
        await session_service.add_session_tool(
            db=db,
            session_id=session_id,
            tool_id=tool_id,
            tenant_id=current_user.tenant_id,
        )


@router.delete(
    "/session/{session_id}/tools/{tool_id}",
    status_code=204,
)
async def remove_session_tool(
    session_id: str,
    tool_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """Deactivate a tool for a session (DB or Redis)."""
    data = await _load_session(db, session_id)
    await _require_session_owner(data, current_user)

    is_temp = data.get("is_temporary", False)

    if is_temp:
        tool_ids: list[str] = list(data.get("active_tool_ids", []))
        if tool_id in tool_ids:
            tool_ids.remove(tool_id)
            data["active_tool_ids"] = tool_ids
            await store_temp_session(session_id, data)
    else:
        await session_service.remove_session_tool(
            db=db,
            session_id=session_id,
            tool_id=tool_id,
        )


# =============================================================================
# Utility
# =============================================================================


def _parse_datetime(val: Any) -> datetime:
    """Parse a datetime value that may be a string or datetime object."""
    if val is None:
        return datetime.utcnow()
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val))
    except (ValueError, TypeError):
        return datetime.utcnow()

