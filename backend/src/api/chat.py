# =============================================================================
# PH Agent Hub — Chat API Router
# =============================================================================
# Session CRUD (permanent via MariaDB + temporary via Redis), message
# sending (agent run), and session-level tool activation.
# =============================================================================

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from ..agents.runner import (
    _get_next_branch_index,
    run_agent,
    run_agent_assistant_only,
    run_agent_stream,
)
from ..core.dependencies import get_current_user, get_db
from ..core.exceptions import (
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from ..core.redis import (
    append_temp_message,
    clear_stream_cancel,
    delete_temp_session,
    get_temp_messages,
    get_temp_session,
    set_stream_cancel,
    store_temp_session,
)
from ..db.orm.messages import Message, MessageFeedback
from ..db.orm.sessions import Session
from ..db.orm.tools import Tool
from ..db.orm.users import User as UserORM
from ..services import session_service, upload_service

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
    thinking_enabled: bool | None = None


class SessionUpdate(BaseModel):
    title: str | None = None
    is_pinned: bool | None = None
    selected_template_id: str | None = None
    selected_prompt_id: str | None = None
    selected_skill_id: str | None = None
    selected_model_id: str | None = None
    thinking_enabled: bool | None = None


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
    thinking_enabled: bool | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    content: str
    file_ids: list[str] | None = None


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


class FeedbackCreate(BaseModel):
    rating: str
    comment: str | None = None


class FeedbackResponse(BaseModel):
    id: str
    message_id: str
    user_id: str
    rating: str
    comment: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FileUploadResponse(BaseModel):
    file_id: str
    original_filename: str
    content_type: str
    size_bytes: int
    created_at: datetime

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
        "thinking_enabled": session.thinking_enabled,
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


async def _inject_file_content(
    db: AsyncSession,
    file_ids: list[str],
    user_message: str,
    session_data: dict,
    current_user: UserORM,
) -> tuple[str, list[str]]:
    """Build file content injection string and return (modified_message, valid_file_ids).

    - Validates DeepSeek + image → 422
    - Extracts text from document uploads
    - Truncates to char budget based on model context_length
    - Returns modified user_message with injected content
    """
    if not file_ids:
        return user_message, []

    # Load FileUpload rows
    from ..db.orm.file_uploads import FileUpload as FileUploadORM

    result = await db.execute(
        select(FileUploadORM).where(
            FileUploadORM.id.in_(file_ids),
            FileUploadORM.user_id == current_user.id,
        )
    )
    uploads = list(result.scalars().all())

    if not uploads:
        return user_message, []

    # Resolve model for provider check and context_length
    model_id = session_data.get("selected_model_id")
    model_orm = None
    if model_id:
        from ..db.orm.models import Model as ModelORM

        model_result = await db.execute(
            select(ModelORM).where(ModelORM.id == model_id)
        )
        model_orm = model_result.scalar_one_or_none()

    provider = getattr(model_orm, "provider", "") if model_orm else ""
    context_length = getattr(model_orm, "context_length", None) if model_orm else None

    # Calculate char budget
    if context_length:
        max_file_chars = min(int(context_length * 3 * 0.4), 100_000)
    else:
        max_file_chars = 20_000

    # Image MIME types
    IMAGE_TYPES = frozenset({
        "image/png", "image/jpeg", "image/gif", "image/webp",
    })

    parts: list[str] = []
    total_chars = 0
    valid_ids: list[str] = []

    for upload in uploads:
        is_image = upload.content_type in IMAGE_TYPES

        if is_image and provider == "deepseek":
            raise ValidationError(
                "This model does not support image attachments. "
                "Please use an OpenAI or Anthropic model for images."
            )

        if is_image:
            # Append placeholder for image-capable models
            parts.append(f"[Image attached: {upload.original_filename}]")
            valid_ids.append(upload.id)
        elif upload.extracted_text:
            # Document: inject extracted text
            header = f"--- Attached File: {upload.original_filename} ---"
            remaining = max_file_chars - total_chars
            if remaining <= 0:
                break
            # Truncate text to remaining budget
            text = upload.extracted_text[:remaining]
            parts.append(f"{header}\n{text}")
            total_chars += len(header) + len(text) + 2  # +2 for newlines
            valid_ids.append(upload.id)
        else:
            # Document with no extracted text (e.g., unsupported PDF) —
            # still link it to the message so it shows in the bubble
            parts.append(
                f"--- Attached File: {upload.original_filename} ---\n"
                "[No text could be extracted from this file]"
            )
            valid_ids.append(upload.id)

    if not parts:
        return user_message, []

    injection = "\n\n".join(parts)
    modified = f"{user_message}\n\n{injection}"
    return modified, valid_ids


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
            "thinking_enabled": body.thinking_enabled,
            "active_tool_ids": body.active_tool_ids or [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
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
            "thinking_enabled": body.thinking_enabled,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
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
            thinking_enabled=body.thinking_enabled,
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
        "thinking_enabled": data.get("thinking_enabled"),
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
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
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
            "thinking_enabled": data.get("thinking_enabled"),
            "created_at": _parse_datetime(data.get("created_at")),
            "updated_at": datetime.now(timezone.utc),
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
            .where(
                Message.session_id == session_id,
                Message.is_deleted == False,  # noqa: E712
            )
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
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """Send a user message and run the agent.

    When the request includes ``Accept: text/event-stream`` the response
    is a Server-Sent Events stream.  Otherwise a plain JSON response is
    returned (Phase 6 backward-compatible path).
    """
    data = await _load_session(db, session_id)
    await _require_session_owner(data, current_user)

    # ---- Auto-title: if session still has the default title, use the
    #      first user message as the title (truncated to 60 chars). ----
    if data.get("title") == "New Chat" and body.content.strip():
        auto_title = body.content.strip()[:60]
        if data.get("is_temporary"):
            data["title"] = auto_title
            await store_temp_session(session_id, data)
        else:
            await session_service.update_session(db, session_id, title=auto_title)
            data["title"] = auto_title

    # Detect streaming request via Accept header
    accept = request.headers.get("accept", "")
    is_streaming = "text/event-stream" in accept.lower()

    # ---- Inject file content into user message --------------------------
    file_ids = body.file_ids or []
    modified_message, valid_file_ids = await _inject_file_content(
        db=db,
        file_ids=file_ids,
        user_message=body.content,
        session_data=data,
        current_user=current_user,
    )

    if is_streaming:
        return await _handle_streaming_message(
            session_id=session_id,
            body=body,
            data=data,
            db=db,
            current_user=current_user,
            modified_message=modified_message,
            valid_file_ids=valid_file_ids,
        )

    # ---- Non-streaming path (Phase 6 backward compat) --------------------
    response_text, assistant_msg_id = await run_agent(
        session_data=data,
        user_message=modified_message,
        db=db,
        current_user=current_user,
        file_ids=valid_file_ids,
    )

    model_id = data.get("selected_model_id")

    return SendMessageResponse(
        message_id=assistant_msg_id,
        content=response_text,
        model_id=model_id,
    )


# ---------------------------------------------------------------------------
# Streaming helpers (Phase 7)
# ---------------------------------------------------------------------------


async def _handle_streaming_message(
    session_id: str,
    body: MessageCreate,
    data: dict[str, Any],
    db: AsyncSession,
    current_user: UserORM,
    modified_message: str = "",
    valid_file_ids: list[str] | None = None,
) -> EventSourceResponse:
    """Assemble and return an SSE EventSourceResponse for a streaming agent run."""
    message_id = str(uuid.uuid4())
    _valid_file_ids = valid_file_ids or []
    _user_message = modified_message or body.content

    async def inner_gen() -> AsyncIterator[dict]:
        """The inner generator that yields SSE event dicts."""
        async for event_dict in run_agent_stream(
            session_data=data,
            user_message=_user_message,
            db=db,
            current_user=current_user,
            message_id=message_id,
            file_ids=_valid_file_ids,
        ):
            yield event_dict

    # Wrap with heartbeat to keep proxy connections alive
    gen = _stream_with_heartbeat(inner_gen(), interval=15)

    return EventSourceResponse(gen, media_type="text/event-stream")


async def _stream_with_heartbeat(
    inner_gen: AsyncIterator[dict],
    interval: int = 15,
) -> AsyncIterator[dict]:
    """Wrap an SSE event generator with heartbeat events.

    Emits ``{"event": "heartbeat", "data": "{}"}`` every *interval*
    seconds when no other event has been emitted, to keep proxy
    connections from closing due to idle timeout.
    """
    while True:
        try:
            event_dict = await asyncio.wait_for(
                inner_gen.__anext__(), timeout=interval
            )
            yield event_dict
        except asyncio.TimeoutError:
            yield {"event": "heartbeat", "data": "{}"}
        except StopAsyncIteration:
            break


@router.delete("/session/{session_id}/stream", status_code=204)
async def cancel_stream(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """Cancel an active streaming agent run for *session_id*.

    Sets a cancellation flag in Redis that the streaming agent runner
    checks on each token yield.  The stream will terminate and partial
    output will be persisted.
    """
    data = await _load_session(db, session_id)
    await _require_session_owner(data, current_user)

    await set_stream_cancel(session_id, ttl=60)
    return Response(status_code=204)


# =============================================================================
# Message Branching (Edit / Regenerate / Soft-Delete) — Phase 8
# =============================================================================


@router.put(
    "/session/{session_id}/message/{message_id}",
    response_model=SendMessageResponse,
)
async def edit_user_message(
    session_id: str,
    message_id: str,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """Edit a user message and re-run the agent, creating a new branch.

    The original user message remains in the DB; a new user message
    with an incremented ``branch_index`` is created, and the agent
    generates a new assistant response off that branch.
    """
    data = await _load_session(db, session_id)
    await _require_session_owner(data, current_user)

    # Reject temporary sessions (no proper message ID tree in Redis)
    if data.get("is_temporary", False):
        raise ValidationError("Message editing is not supported for temporary sessions")

    # Load the original user message
    msg_result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.session_id == session_id,
        )
    )
    original_msg = msg_result.scalar_one_or_none()
    if original_msg is None:
        raise NotFoundError("Message not found")
    if original_msg.sender != "user":
        raise ValidationError("Only user messages can be edited")

    # Calculate next branch index at the same parent level
    next_branch = await _get_next_branch_index(
        db=db,
        session_id=session_id,
        parent_message_id=original_msg.parent_message_id,
    )

    # Run agent with branching
    response_text, assistant_msg_id = await run_agent(
        session_data=data,
        user_message=body.content,
        db=db,
        current_user=current_user,
        parent_message_id=original_msg.parent_message_id,
        user_branch_index=next_branch,
    )

    model_id = data.get("selected_model_id")
    return SendMessageResponse(
        message_id=assistant_msg_id,
        content=response_text,
        model_id=model_id,
    )


@router.delete(
    "/session/{session_id}/message/{message_id}",
    status_code=204,
)
async def delete_message(
    session_id: str,
    message_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """Soft-delete a message (sets ``is_deleted=True``)."""
    data = await _load_session(db, session_id)
    await _require_session_owner(data, current_user)

    if data.get("is_temporary", False):
        raise ValidationError("Message deletion is not supported for temporary sessions")

    msg_result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.session_id == session_id,
        )
    )
    msg = msg_result.scalar_one_or_none()
    if msg is None:
        raise NotFoundError("Message not found")

    msg.is_deleted = True

    # Cascade: delete attached file uploads (MinIO objects + DB rows)
    await upload_service.delete_uploads_for_message(db, message_id)

    await db.commit()
    return Response(status_code=204)


@router.post(
    "/session/{session_id}/message/{message_id}/regenerate",
    response_model=SendMessageResponse,
)
async def regenerate_assistant_message(
    session_id: str,
    message_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """Regenerate an assistant response, creating a new branch.

    Uses the parent user message's text to re-run the agent, then
    persists only the new assistant message (no duplicate user message).
    """
    data = await _load_session(db, session_id)
    await _require_session_owner(data, current_user)

    if data.get("is_temporary", False):
        raise ValidationError("Regeneration is not supported for temporary sessions")

    # Load the assistant message to regenerate
    msg_result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.session_id == session_id,
        )
    )
    assistant_msg = msg_result.scalar_one_or_none()
    if assistant_msg is None:
        raise NotFoundError("Message not found")
    if assistant_msg.sender != "assistant":
        raise ValidationError("Only assistant messages can be regenerated")

    # Load the parent user message
    if assistant_msg.parent_message_id is None:
        raise ValidationError(
            "Cannot regenerate: assistant message has no parent user message"
        )

    parent_result = await db.execute(
        select(Message).where(Message.id == assistant_msg.parent_message_id)
    )
    parent_user_msg = parent_result.scalar_one_or_none()
    if parent_user_msg is None or parent_user_msg.sender != "user":
        raise ValidationError(
            "Cannot regenerate: parent message not found or is not a user message"
        )

    # Extract user text from the parent message content
    user_text = ""
    if parent_user_msg.content and isinstance(parent_user_msg.content, list):
        for item in parent_user_msg.content:
            if isinstance(item, dict) and item.get("type") == "text":
                user_text = item.get("text", "")
                break
    if not user_text:
        raise ValidationError(
            "Cannot regenerate: parent user message has no text content"
        )

    # Calculate next branch index at the parent level
    next_branch = await _get_next_branch_index(
        db=db,
        session_id=session_id,
        parent_message_id=parent_user_msg.id,
    )

    # Run agent (assistant-only, no duplicate user message)
    response_text, new_assistant_msg_id = await run_agent_assistant_only(
        session_data=data,
        user_message_text=user_text,
        user_message_id=parent_user_msg.id,
        db=db,
        current_user=current_user,
        assistant_parent_message_id=parent_user_msg.id,
        assistant_branch_index=next_branch,
    )

    model_id = data.get("selected_model_id")
    return SendMessageResponse(
        message_id=new_assistant_msg_id,
        content=response_text,
        model_id=model_id,
    )


# =============================================================================
# Message Feedback — Phase 8
# =============================================================================


@router.post(
    "/session/{session_id}/message/{message_id}/feedback",
    response_model=FeedbackResponse,
    status_code=201,
)
async def submit_feedback(
    session_id: str,
    message_id: str,
    body: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """Submit feedback (up/down) for an assistant message."""
    data = await _load_session(db, session_id)
    await _require_session_owner(data, current_user)

    # Validate rating
    if body.rating not in ("up", "down"):
        raise ValidationError("Rating must be 'up' or 'down'")

    # Load message
    msg_result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.session_id == session_id,
        )
    )
    msg = msg_result.scalar_one_or_none()
    if msg is None:
        raise NotFoundError("Message not found")
    if msg.sender != "assistant":
        raise ValidationError("Feedback can only be submitted for assistant messages")

    feedback = MessageFeedback(
        message_id=message_id,
        user_id=current_user.id,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)

    return FeedbackResponse.model_validate(feedback)


# =============================================================================
# Session Search — Phase 8
# =============================================================================


@router.get(
    "/sessions/search",
    response_model=list[SessionResponse],
)
async def search_sessions(
    q: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """Full-text search across session titles and message content.

    Query is scoped to the authenticated user's tenant and user ID.
    Uses FULLTEXT index on ``sessions.title`` and ``LIKE`` on
    ``messages.content`` (JSON column).
    """
    if not q or not q.strip():
        raise ValidationError("Search query 'q' is required")

    search_term = f"%{q.strip()}%"

    # Search sessions by title (FULLTEXT) and by message content (LIKE)
    from sqlalchemy import text, type_coerce, String as SAString

    # FULLTEXT on sessions.title
    title_stmt = (
        select(Session)
        .where(
            Session.user_id == current_user.id,
            Session.tenant_id == current_user.tenant_id,
            Session.is_temporary == False,  # noqa: E712
            text("MATCH(sessions.title) AGAINST(:query IN NATURAL LANGUAGE MODE)"),
        )
        .params(query=q.strip())
    )

    # LIKE fallback on sessions.title (covers cases where FULLTEXT can't)
    like_stmt = (
        select(Session)
        .where(
            Session.user_id == current_user.id,
            Session.tenant_id == current_user.tenant_id,
            Session.is_temporary == False,  # noqa: E712
            Session.title.ilike(search_term),
        )
    )

    # Search sessions via message content (LIKE on JSON column)
    msg_stmt = (
        select(Session)
        .join(Message, Message.session_id == Session.id)
        .where(
            Session.user_id == current_user.id,
            Session.tenant_id == current_user.tenant_id,
            Session.is_temporary == False,  # noqa: E712
            Message.is_deleted == False,  # noqa: E712
            type_coerce(Message.content, SAString).ilike(search_term),
        )
    )

    # Execute all three queries
    title_results = await db.execute(title_stmt)
    like_results = await db.execute(like_stmt)
    msg_results = await db.execute(msg_stmt)

    # Deduplicate by session ID (union of all three)
    seen: set[str] = set()
    sessions: list[Session] = []
    for s in (
        list(title_results.scalars().all())
        + list(like_results.scalars().all())
        + list(msg_results.scalars().all())
    ):
        if s.id not in seen:
            seen.add(s.id)
            sessions.append(s)

    return [SessionResponse.model_validate(s) for s in sessions]


# =============================================================================
# File Uploads — Phase 8
# =============================================================================


@router.post(
    "/session/{session_id}/upload",
    response_model=FileUploadResponse,
    status_code=201,
)
async def upload_file(
    session_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """Upload a file to a session (stored in MinIO)."""
    data = await _load_session(db, session_id)
    await _require_session_owner(data, current_user)

    if not file.filename:
        raise ValidationError("File must have a filename")

    file_bytes = await file.read()
    content_type = file.content_type or "application/octet-stream"

    upload = await upload_service.create_upload(
        db=db,
        session_data=data,
        current_user=current_user,
        file_bytes=file_bytes,
        original_filename=file.filename,
        content_type=content_type,
    )

    return FileUploadResponse(
        file_id=upload.id,
        original_filename=upload.original_filename,
        content_type=upload.content_type,
        size_bytes=upload.size_bytes,
        created_at=upload.created_at,
    )


@router.get(
    "/session/{session_id}/uploads",
    response_model=list[FileUploadResponse],
)
async def list_uploads(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """List all file uploads for a session."""
    data = await _load_session(db, session_id)
    await _require_session_owner(data, current_user)

    uploads = await upload_service.list_uploads(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
    )
    return [
        FileUploadResponse(
            file_id=u.id,
            original_filename=u.original_filename,
            content_type=u.content_type,
            size_bytes=u.size_bytes,
            created_at=u.created_at,
        )
        for u in uploads
    ]


@router.get(
    "/session/{session_id}/upload/{file_id}/url",
)
async def get_upload_url(
    session_id: str,
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """Generate a presigned download URL for an uploaded file."""
    data = await _load_session(db, session_id)
    await _require_session_owner(data, current_user)

    url = await upload_service.generate_presigned_url(
        db=db,
        file_id=file_id,
        user_id=current_user.id,
    )
    return {"url": url}


@router.delete(
    "/session/{session_id}/upload/{file_id}",
    status_code=204,
)
async def delete_upload(
    session_id: str,
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """Delete a file upload (MinIO object + DB row)."""
    data = await _load_session(db, session_id)
    await _require_session_owner(data, current_user)

    await upload_service.delete_upload(
        db=db,
        file_id=file_id,
        user_id=current_user.id,
    )
    return Response(status_code=204)


@router.get(
    "/session/{session_id}/message/{message_id}/uploads",
    response_model=list[FileUploadResponse],
)
async def list_message_uploads(
    session_id: str,
    message_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """List all file uploads linked to a specific message."""
    data = await _load_session(db, session_id)
    await _require_session_owner(data, current_user)

    uploads = await upload_service.list_uploads_for_message(
        db=db,
        message_id=message_id,
    )
    return [
        FileUploadResponse(
            file_id=u.id,
            original_filename=u.original_filename,
            content_type=u.content_type,
            size_bytes=u.size_bytes,
            created_at=u.created_at,
        )
        for u in uploads
    ]


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
        logger.warning("_parse_datetime received None, using current time")
        return datetime.now(timezone.utc)
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val))
    except (ValueError, TypeError):
        logger.warning("_parse_datetime failed to parse '%s', using current time", val)
        return datetime.now(timezone.utc)

