# =============================================================================
# PH Agent Hub — Agent Runner
# =============================================================================
# Per-request MAF agent assembly and execution.
#
# Primary entry points:
#   ``run_agent()``        — non-streaming (Phase 6)
#   ``run_agent_stream()`` — SSE streaming (Phase 7)
#
# Resolution chain (model):
#   session.selected_model_id → skill.default_model_id
#   → template.default_model_id → ValidationError
#
# System prompt construction:
#   template.system_prompt + "\\n\\n---\\n\\n" + prompt.content (when both exist)
# =============================================================================

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.exceptions import ValidationError, NotFoundError
from ..core.redis import (
    append_temp_message,
    check_stream_cancel,
    clear_stream_cancel,
    get_temp_session,
)
from ..db.orm.erpnext_instances import ERPNextInstance
from ..db.orm.messages import Message
from ..db.orm.models import Model
from ..db.orm.prompts import Prompt
from ..db.orm.sessions import Session, SessionActiveTool
from ..db.orm.skills import Skill
from ..db.orm.templates import Template
from ..db.orm.tools import Tool
from ..db.orm.users import User
from ..models.base import get_chat_client
from ..services.usage_service import write_usage_log

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session config resolution (shared by run_agent / run_agent_stream)
# ---------------------------------------------------------------------------


@dataclass
class SessionConfig:
    """Resolved configuration for a single agent run."""
    model: Model
    model_client: Any
    system_prompt: str
    skill: Skill | None
    active_tool_callables: list
    execution_type: str
    agent_name: str


async def _resolve_session_config(
    db: AsyncSession,
    session_data: dict,
    tenant_id: str,
    user: User | None = None,
) -> SessionConfig:
    """Resolve model, system prompt, skill, tools, execution type, and agent name.

    Centralises the resolution chain shared by ``run_agent()``,
    ``run_agent_stream()``, and ``run_agent_assistant_only()``.
    """
    # 1. Resolve model
    model = await _resolve_model(db, session_data, user)
    model_client = get_chat_client(model)

    # 2. Build system prompt
    system_prompt = await _build_system_prompt(db, session_data)

    # 3. Resolve skill
    skill = await _resolve_skill(db, session_data)

    # 4. Resolve active tools
    active_tool_callables = await _resolve_tool_callables(
        db, session_data, tenant_id
    )

    # 5. Determine execution type and name
    execution_type = skill.execution_type if skill else "agent"
    # Normalize: workflow_based → workflow, prompt_based → agent
    if execution_type == "workflow_based":
        execution_type = "workflow"
    if execution_type == "prompt_based":
        execution_type = "agent"
    agent_name = skill.title if skill else "assistant"

    # 6. Apply DeepSeek middleware
    if model.provider.lower() == "deepseek":
        from .deepseek_patch import apply_deepseek_patches
        apply_deepseek_patches()

    return SessionConfig(
        model=model,
        model_client=model_client,
        system_prompt=system_prompt,
        skill=skill,
        active_tool_callables=active_tool_callables,
        execution_type=execution_type,
        agent_name=agent_name,
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def run_agent(
    session_data: dict,
    user_message: str,
    db: AsyncSession,
    current_user: User,
    parent_message_id: str | None = None,
    user_branch_index: int = 0,
) -> tuple[str, str]:
    """Assemble and run a MAF agent for a single user message.

    Args:
        session_data: Unified session dict (from DB or Redis).
        user_message: The text the user sent.
        db: Active async DB session.
        current_user: The authenticated user.
        parent_message_id: If editing/regenerating, the parent message ID
            for the branch point.
        user_branch_index: Branch index for this user message (default 0
            for the root of the conversation).

    Returns:
        A tuple of (assistant response text, assistant message ID).
    """
    tenant_id = current_user.tenant_id
    session_id = session_data["id"]
    is_temporary = session_data.get("is_temporary", False)

    # ---- 1-6. Resolve session config ------------------------------------
    cfg = await _resolve_session_config(db, session_data, tenant_id, current_user)

    # ---- 7. Run agent or workflow ----------------------------------------
    raw_response: str

    try:
        if cfg.execution_type == "workflow":
            raw_response, tokens_in, tokens_out = await _run_workflow(
                model=cfg.model,
                skill=cfg.skill,
                model_client=cfg.model_client,
                system_prompt=cfg.system_prompt,
                tools=cfg.active_tool_callables,
                user_message=user_message,
                agent_name=cfg.agent_name,
            )
        else:
            raw_response, tokens_in, tokens_out = await _run_agent(
                model=cfg.model,
                model_client=cfg.model_client,
                system_prompt=cfg.system_prompt,
                tools=cfg.active_tool_callables,
                user_message=user_message,
                agent_name=cfg.agent_name,
            )
    except Exception as exc:
        logger.error("Agent run failed: %s", exc)
        raise ValidationError(
            f"Agent execution failed: {exc}"
        ) from exc

    # ---- 8. Stabilise DeepSeek output -----------------------------------
    if cfg.model.provider.lower() == "deepseek" and settings.DEEPSEEK_STRIP_REASONING:
        from .stabilizer import stabilize_text
        raw_response = stabilize_text(raw_response)

    # ---- 9. Persist messages --------------------------------------------
    _user_msg_id, assistant_msg_id = await _persist_messages(
        db=db,
        session_id=session_id,
        is_temporary=is_temporary,
        user_message=user_message,
        assistant_response=raw_response,
        model_id=cfg.model.id,
        parent_message_id=parent_message_id,
        user_branch_index=user_branch_index,
    )

    # ---- 10. Write usage log --------------------------------------------
    try:
        await write_usage_log(
            db,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            model_id=cfg.model.id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
    except Exception:
        logger.exception("Failed to write usage log (non-streaming)")

    return raw_response, assistant_msg_id


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------


async def _resolve_model(
    db: AsyncSession, session_data: dict, user: User | None = None
) -> Model:
    """Resolve the model client following the fallback chain.

    Resolution order:
    1. session.selected_model_id
    2. user.default_model_id
    3. skill.default_model_id
    4. template.default_model_id
    5. first accessible enabled model for the user
    6. ValidationError
    """
    tenant_id = session_data.get("tenant_id", "")
    user_id = session_data.get("user_id", "")

    # 1. session.selected_model_id
    model_id = session_data.get("selected_model_id")
    if model_id:
        result = await db.execute(select(Model).where(Model.id == model_id))
        model = result.scalar_one_or_none()
        if model:
            return model

    # 2. user.default_model_id
    if user and user.default_model_id:
        result = await db.execute(
            select(Model).where(Model.id == user.default_model_id)
        )
        model = result.scalar_one_or_none()
        if model:
            return model

    # 3. skill.default_model_id
    skill_id = session_data.get("selected_skill_id")
    if skill_id:
        result = await db.execute(select(Skill).where(Skill.id == skill_id))
        skill = result.scalar_one_or_none()
        if skill and skill.default_model_id:
            result = await db.execute(
                select(Model).where(Model.id == skill.default_model_id)
            )
            model = result.scalar_one_or_none()
            if model:
                return model

    # 4. template.default_model_id
    template_id = session_data.get("selected_template_id")
    if template_id:
        result = await db.execute(
            select(Template).where(Template.id == template_id)
        )
        template = result.scalar_one_or_none()
        if template and template.default_model_id:
            result = await db.execute(
                select(Model).where(Model.id == template.default_model_id)
            )
            model = result.scalar_one_or_none()
            if model:
                return model

    # 5. first accessible enabled model
    from ..services.model_service import list_models as _svc_list_models
    models = await _svc_list_models(
        db, tenant_id=tenant_id, user_id=user_id
    )
    enabled = [m for m in models if m.enabled]
    if enabled:
        return enabled[0]

    raise ValidationError(
        "No model configured. Please select a model for this session, "
        "or configure a default model on your profile, skill, or template."
    )


async def _build_system_prompt(
    db: AsyncSession, session_data: dict
) -> str:
    """Build the system prompt from template + optional prompt."""
    template_id = session_data.get("selected_template_id")
    prompt_id = session_data.get("selected_prompt_id")

    parts: list[str] = []

    # Template system prompt
    if template_id:
        result = await db.execute(
            select(Template).where(Template.id == template_id)
        )
        template = result.scalar_one_or_none()
        if template:
            parts.append(template.system_prompt)

    # Prompt content (appended if both exist)
    if prompt_id:
        result = await db.execute(
            select(Prompt).where(Prompt.id == prompt_id)
        )
        prompt = result.scalar_one_or_none()
        if prompt:
            parts.append(prompt.content)

    if parts:
        return "\n\n---\n\n".join(parts)

    return "You are a helpful assistant."


async def _resolve_skill(
    db: AsyncSession, session_data: dict
) -> Skill | None:
    """Load the selected skill, if any."""
    skill_id = session_data.get("selected_skill_id")
    if not skill_id:
        return None

    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    return result.scalar_one_or_none()


async def _resolve_tool_callables(
    db: AsyncSession,
    session_data: dict,
    tenant_id: str,
) -> list:
    """Resolve active tools into MAF tool callables."""
    session_id = session_data["id"]
    is_temporary = session_data.get("is_temporary", False)

    # Load Tool ORM records
    tools: list[Tool] = []

    if is_temporary:
        # Temp session: use active_tool_ids from the Redis blob
        tool_ids = session_data.get("active_tool_ids", [])
        if tool_ids:
            result = await db.execute(
                select(Tool).where(
                    Tool.id.in_(tool_ids),
                    Tool.tenant_id == tenant_id,
                    Tool.enabled == True,  # noqa: E712
                )
            )
            tools = list(result.scalars().all())
    else:
        # Permanent session: query the join table
        result = await db.execute(
            select(Tool)
            .join(SessionActiveTool, SessionActiveTool.tool_id == Tool.id)
            .where(
                SessionActiveTool.session_id == session_id,
                Tool.tenant_id == tenant_id,
                Tool.enabled == True,  # noqa: E712
            )
        )
        tools = list(result.scalars().all())

    # Build callables for each tool
    callables: list = []
    for tool in tools:
        tool_callables = await _build_tool_callables(db, tool, tenant_id)
        callables.extend(tool_callables)

    return callables


async def _build_tool_callables(
    db: AsyncSession,
    tool: Tool,
    tenant_id: str,
) -> list:
    """Dispatch on tool.type to the appropriate factory."""
    if tool.type == "erpnext":
        return await _build_erpnext_callables(db, tool, tenant_id)
    elif tool.type == "membrane":
        from ..tools.membrane import build_membrane_tools
        return build_membrane_tools(tool.config or {})
    elif tool.type == "custom":
        # Stub for Phase 6
        return []
    else:
        logger.warning("Unknown tool type '%s' for tool %s", tool.type, tool.id)
        return []


async def _build_erpnext_callables(
    db: AsyncSession,
    tool: Tool,
    tenant_id: str,
) -> list:
    """Build ERPNext tool callables for a given Tool record.

    Looks up the ERPNextInstance via ``tool.config.erpnext_instance_id``.
    Falls back to the first enabled instance for the tenant.
    """
    from ..tools.erpnext import build_erpnext_tools

    config = tool.config or {}
    instance_id = config.get("erpnext_instance_id")

    instance: ERPNextInstance | None = None

    if instance_id:
        result = await db.execute(
            select(ERPNextInstance).where(
                ERPNextInstance.id == instance_id,
                ERPNextInstance.tenant_id == tenant_id,
            )
        )
        instance = result.scalar_one_or_none()

    if instance is None:
        # Fall back to first enabled instance for the tenant
        result = await db.execute(
            select(ERPNextInstance).where(
                ERPNextInstance.tenant_id == tenant_id,
            )
        )
        instance = result.scalars().first()
        if instance is None:
            raise NotFoundError(
                f"No ERPNext instance found for tenant '{tenant_id}'. "
                "Create one via POST /admin/erpnext-instances."
            )

    return build_erpnext_tools(
        base_url=instance.base_url,
        api_key=instance.api_key,
        api_secret=instance.api_secret,
    )


# ---------------------------------------------------------------------------
# Agent / Workflow execution
# ---------------------------------------------------------------------------


async def _run_agent(
    model: Model,
    model_client: Any,
    system_prompt: str,
    tools: list,
    user_message: str,
    agent_name: str,
) -> tuple[str, int, int]:
    """Run a simple MAF Agent.

    Returns:
        A tuple of (response_text, tokens_in, tokens_out).
    """
    from agent_framework import Agent

    agent = Agent(
        client=model_client,
        name=agent_name,
        instructions=system_prompt,
        tools=tools,
    )

    result = await agent.run(user_message)

    # Extract token counts (best-effort)
    tokens_in, tokens_out = _extract_token_counts(result)

    # result could be a string or a structured object
    if isinstance(result, str):
        return result, tokens_in, tokens_out

    # MAF may return an object with a .final_output or .content attribute
    if hasattr(result, "final_output"):
        return str(result.final_output), tokens_in, tokens_out
    if hasattr(result, "content"):
        return str(result.content), tokens_in, tokens_out

    return str(result), tokens_in, tokens_out


async def _run_workflow(
    model: Model,
    skill: Skill,
    model_client: Any,
    system_prompt: str,
    tools: list,
    user_message: str,
    agent_name: str,
) -> tuple[str, int, int]:
    """Run a MAF Workflow via the registry.

    Returns:
        A tuple of (response_text, tokens_in, tokens_out).
    """
    from .registry import get_registered

    if skill is None or not skill.maf_target_key:
        raise ValidationError("Workflow execution requires a skill with a maf_target_key")

    target = get_registered(skill.maf_target_key)
    if target is None:
        raise NotFoundError(
            f"No registered workflow for key '{skill.maf_target_key}'. "
            "Register a workflow module in src/agents/workflows/."
        )

    # Stub: fall back to agent execution if workflow runner not available
    logger.warning(
        "Workflow execution not fully implemented for key '%s'; falling back to agent.",
        skill.maf_target_key,
    )
    return await _run_agent(
        model=model,
        model_client=model_client,
        system_prompt=system_prompt,
        tools=tools,
        user_message=user_message,
        agent_name=agent_name,
    )


# ---------------------------------------------------------------------------
# Message persistence
# ---------------------------------------------------------------------------


async def _persist_user_message(
    db: AsyncSession,
    session_id: str,
    is_temporary: bool,
    user_message: str,
    parent_message_id: str | None = None,
    user_branch_index: int = 0,
) -> str:
    """Persist just the user message, returning its ID.

    Used by the streaming path so the user message is visible even if
    the agent run fails."""
    content = [{"type": "text", "text": user_message}]
    user_msg_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    if is_temporary:
        await append_temp_message(
            session_id,
            {
                "id": user_msg_id,
                "sender": "user",
                "content": content,
                "parent_message_id": parent_message_id,
                "branch_index": user_branch_index,
                "created_at": now.isoformat(),
            },
        )
    else:
        msg = Message(
            id=user_msg_id,
            session_id=session_id,
            sender="user",
            content=content,
            parent_message_id=parent_message_id,
            branch_index=user_branch_index,
            created_at=now,
        )
        db.add(msg)
        await db.commit()

    return user_msg_id


async def _persist_assistant_message(
    db: AsyncSession,
    session_id: str,
    is_temporary: bool,
    assistant_response: str,
    model_id: str,
    parent_message_id: str,
) -> str:
    """Persist just the assistant message, returning its ID."""
    content = [{"type": "text", "text": assistant_response}]
    assistant_msg_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    if is_temporary:
        await append_temp_message(
            session_id,
            {
                "id": assistant_msg_id,
                "sender": "assistant",
                "content": content,
                "model_id": model_id,
                "parent_message_id": parent_message_id,
                "branch_index": 0,
                "created_at": now.isoformat(),
            },
        )
    else:
        msg = Message(
            id=assistant_msg_id,
            session_id=session_id,
            sender="assistant",
            content=content,
            model_id=model_id,
            parent_message_id=parent_message_id,
            branch_index=0,
            created_at=now,
        )
        db.add(msg)
        await db.commit()

    return assistant_msg_id


async def _persist_messages(
    db: AsyncSession,
    session_id: str,
    is_temporary: bool,
    user_message: str,
    assistant_response: str,
    model_id: str,
    parent_message_id: str | None = None,
    user_branch_index: int = 0,
) -> tuple[str, str]:
    """Persist the user message and assistant response.

    Returns:
        A tuple of (user_message_id, assistant_message_id).
    """
    user_msg_content = [{"type": "text", "text": user_message}]
    assistant_msg_content = [{"type": "text", "text": assistant_response}]

    if is_temporary:
        # Store in Redis
        user_msg_id = str(uuid.uuid4())
        assistant_msg_id = str(uuid.uuid4())
        await append_temp_message(
            session_id,
            {
                "id": user_msg_id,
                "sender": "user",
                "content": user_msg_content,
                "parent_message_id": parent_message_id,
                "branch_index": user_branch_index,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        await append_temp_message(
            session_id,
            {
                "id": assistant_msg_id,
                "sender": "assistant",
                "content": assistant_msg_content,
                "model_id": model_id,
                "parent_message_id": user_msg_id,
                "branch_index": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return user_msg_id, assistant_msg_id
    else:
        # Store in MariaDB
        now = datetime.now(timezone.utc)
        user_msg_id = str(uuid.uuid4())
        user_msg = Message(
            id=user_msg_id,
            session_id=session_id,
            sender="user",
            content=user_msg_content,
            parent_message_id=parent_message_id,
            branch_index=user_branch_index,
            created_at=now,
        )
        db.add(user_msg)
        await db.flush()

        assistant_msg_id = str(uuid.uuid4())
        assistant_msg = Message(
            id=assistant_msg_id,
            session_id=session_id,
            sender="assistant",
            content=assistant_msg_content,
            model_id=model_id,
            parent_message_id=user_msg_id,
            branch_index=0,
            created_at=datetime.now(timezone.utc),
        )
        db.add(assistant_msg)
        await db.commit()

        return user_msg_id, assistant_msg_id


# =============================================================================
# Phase 7 — Streaming Agent Runner
# =============================================================================


class ThinkBlockStreamFilter:
    """Stateful, streaming-aware ``<think>...</think>`` content filter.

    Wraps an async token iterator and suppresses all content between
    ``<think>`` and ``</think>`` tags.  Buffers partial tag text so that
    incomplete tag boundaries never emit stray ``<think`` characters
    into the output stream.

    Only needed when ``model.provider == "deepseek"`` and
    ``settings.DEEPSEEK_STRIP_REASONING`` is True.
    """

    _OPEN = "<think"
    _CLOSE = "</think>"

    def __init__(self, token_iter: AsyncIterator[str]) -> None:
        self._iter = token_iter
        self._buffer: str = ""
        self._inside_think: bool = False

    def __aiter__(self) -> "ThinkBlockStreamFilter":
        return self

    async def __anext__(self) -> str:
        while True:
            # Drain buffer first
            if self._buffer:
                ch = self._buffer[0]
                self._buffer = self._buffer[1:]
            else:
                try:
                    ch = await self._iter.__anext__()
                except StopAsyncIteration:
                    # Flush any remaining buffered text that is not inside
                    # a think block.  If we're still inside a think block
                    # the closing tag was never emitted — discard.
                    if self._buffer and not self._inside_think:
                        remaining = self._buffer
                        self._buffer = ""
                        return remaining
                    raise

            if self._inside_think:
                # Accumulate until we see the closing tag
                self._buffer = ch + self._buffer  # prepend for tag matching
                idx = self._buffer.find(self._CLOSE)
                if idx != -1:
                    # Found closing tag — discard everything up to & including it
                    self._buffer = self._buffer[idx + len(self._CLOSE):]
                    self._inside_think = False
                # else: keep buffering inside the think block
                continue

            # Outside think block — check for opening tag
            self._buffer = ch + self._buffer
            idx = self._buffer.find(self._OPEN)
            if idx != -1:
                # Emit everything before the opening tag
                before = self._buffer[:idx]
                self._buffer = self._buffer[idx + len(self._OPEN):]
                self._inside_think = True
                if before:
                    return before
                # Continue loop — will enter _inside_think branch
                continue

            # No tag found — emit oldest character
            if len(self._buffer) > len(self._OPEN):
                # Buffer is large enough to be sure no partial <think is coming
                emit = self._buffer[:-len(self._OPEN) + 1]
                self._buffer = self._buffer[-len(self._OPEN) + 1:]
                return emit

            # Buffer still small — fetch more
            continue


async def run_agent_stream(
    session_data: dict,
    user_message: str,
    db: AsyncSession,
    current_user: User,
    message_id: str,
) -> AsyncIterator[dict]:
    """Assemble and run a MAF agent, yielding typed SSE event dicts.

    Each yielded dict has the shape ``{"event": str, "data": str}``
    where ``data`` is a JSON-encoded string matching the schema in
    ``docs/streaming-protocol.md §5``.

    Args:
        session_data: Unified session dict (from DB or Redis).
        user_message: The text the user sent.
        db: Active async DB session.
        current_user: The authenticated user.
        message_id: Pre-generated UUID for the assistant message (used
            for client-side correlation across all events).

    Yields:
        Dicts with ``event`` and ``data`` keys suitable for
        ``EventSourceResponse``.
    """
    tenant_id = current_user.tenant_id
    session_id = session_data["id"]
    is_temporary = session_data.get("is_temporary", False)

    accumulated_text: str = ""
    step_index: int = 0
    total_tokens: int = 0
    _stream_token_info: dict = {}  # mutated by _run_agent_stream to propagate token counts
    cfg = None

    # Persist the user message immediately so it's always visible,
    # even if the agent run fails.
    user_msg_id = await _persist_user_message(
        db=db,
        session_id=session_id,
        is_temporary=is_temporary,
        user_message=user_message,
    )

    try:
        # ---- 1-6. Resolve session config --------------------------------
        cfg = await _resolve_session_config(db, session_data, tenant_id, current_user)

        # ---- 7. Run agent or workflow (streaming) ------------------------
        if cfg.execution_type == "workflow":
            stream = _run_workflow_stream(
                model=cfg.model,
                skill=cfg.skill,
                model_client=cfg.model_client,
                system_prompt=cfg.system_prompt,
                tools=cfg.active_tool_callables,
                user_message=user_message,
                agent_name=cfg.agent_name,
                session_id=session_id,
                message_id=message_id,
                token_counts=_stream_token_info,
            )
        else:
            stream = _run_agent_stream(
                model=cfg.model,
                model_client=cfg.model_client,
                system_prompt=cfg.system_prompt,
                tools=cfg.active_tool_callables,
                user_message=user_message,
                agent_name=cfg.agent_name,
                session_id=session_id,
                message_id=message_id,
                token_counts=_stream_token_info,
            )

        async for event_dict in stream:
            # Check for cancellation before each yield
            if await check_stream_cancel(session_id):
                await clear_stream_cancel(session_id)
                logger.warning(
                    "Stream cancelled for session %s — partial content will be persisted",
                    session_id,
                )
                # Persist whatever we have so far
                accumulated_text = _maybe_accumulate_text(
                    event_dict, accumulated_text
                )
                break

            # Accumulate text from token events
            accumulated_text = _maybe_accumulate_text(
                event_dict, accumulated_text
            )

            yield event_dict

    except Exception as exc:
        logger.exception("Agent stream failed for session %s", session_id)
        yield {
            "event": "error",
            "data": json.dumps({
                "session_id": session_id,
                "message_id": message_id,
                "code": _exc_to_error_code(exc),
                "message": str(exc),
            }),
        }
        return  # Don't proceed to message_complete on error

    # ---- 8. Stabilise DeepSeek output (on full text) ---------------------
    if (
        cfg.model.provider.lower() == "deepseek"
        and settings.DEEPSEEK_STRIP_REASONING
    ):
        from .stabilizer import stabilize_text
        accumulated_text = stabilize_text(accumulated_text)

    # ---- 9. Extract token counts from stream final response -------------
    tokens_in, tokens_out = _stream_token_info.get("in", 0), _stream_token_info.get("out", 0)

    # ---- 10. Persist assistant message ------------------------------------
    await _persist_assistant_message(
        db=db,
        session_id=session_id,
        is_temporary=is_temporary,
        assistant_response=accumulated_text,
        model_id=cfg.model.id,
        parent_message_id=user_msg_id,
    )

    # ---- 11. Write usage log ---------------------------------------------
    try:
        await write_usage_log(
            db,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            model_id=cfg.model.id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
    except Exception:
        logger.exception("Failed to write usage log (streaming)")

    # ---- 12. Emit message_complete ---------------------------------------
    yield {
        "event": "message_complete",
        "data": json.dumps({
            "session_id": session_id,
            "message_id": message_id,
            "branch_index": 0,
            "total_tokens": total_tokens,
            "model_id": cfg.model.id,
        }),
    }


# ---------------------------------------------------------------------------
# Streaming agent / workflow execution helpers
# ---------------------------------------------------------------------------


async def _run_agent_stream(
    model: Model,
    model_client: Any,
    system_prompt: str,
    tools: list,
    user_message: str,
    agent_name: str,
    session_id: str,
    message_id: str,
    token_counts: dict | None = None,
) -> AsyncIterator[dict]:
    """Run a MAF Agent in streaming mode, yielding SSE event dicts."""
    from agent_framework import Agent

    agent = Agent(
        client=model_client,
        name=agent_name,
        instructions=system_prompt,
        tools=tools,
    )

    response_stream = agent.run(user_message, stream=True)

    # Per-stream think filter — instantiated once so state is isolated
    think_filter: _ThinkFilter | None = None
    if (
        model.provider.lower() == "deepseek"
        and settings.DEEPSEEK_STRIP_REASONING
    ):
        think_filter = _ThinkFilter()

    step_index = 0
    async for update in response_stream:
        # Check each content item in the update
        for content in update.contents:
            content_type = getattr(content, "type", None)

            if content_type == "text":
                delta = getattr(content, "text", "")
                if delta:
                    if think_filter is not None:
                        delta = think_filter.feed(delta)

                    if delta:
                        yield _sse_event("token", {
                            "delta": delta,
                        }, session_id=session_id, message_id=message_id)
            elif content_type in ("function_call", "tool_call"):
                tool_call_id = getattr(content, "call_id", None) or str(uuid.uuid4())
                tool_name = getattr(content, "name", "unknown")
                arguments = getattr(content, "arguments", None)
                if arguments is not None:
                    try:
                        arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
                    except (json.JSONDecodeError, TypeError):
                        arguments = str(arguments)

                yield _sse_event("tool_start", {
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "arguments": arguments,
                }, session_id=session_id, message_id=message_id)
            elif content_type in ("function_result", "tool_result"):
                tool_call_id = getattr(content, "call_id", None) or ""
                tool_name = getattr(content, "name", "unknown")
                output = getattr(content, "output", None) or getattr(content, "result", None)
                success = True  # MAF surfaces errors via separate content types
                result_summary = _summarise_tool_result(output)

                yield _sse_event("tool_result", {
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "success": success,
                    "result_summary": result_summary,
                }, session_id=session_id, message_id=message_id)

                step_index += 1
                yield _sse_event("step_complete", {
                    "step_index": step_index,
                    "total_steps_so_far": step_index,
                }, session_id=session_id, message_id=message_id)

    # After stream is exhausted, get final response for token counts
    try:
        final = await response_stream.get_final_response()
        if token_counts is not None:
            usage = getattr(final, "usage", None)
            if usage:
                token_counts["in"] = getattr(usage, "input_tokens", 0) or 0
                token_counts["out"] = getattr(usage, "output_tokens", 0) or 0
    except Exception:
        pass  # Token count is best-effort for Phase 7


async def _run_workflow_stream(
    model: Model,
    skill: Any,
    model_client: Any,
    system_prompt: str,
    tools: list,
    user_message: str,
    agent_name: str,
    session_id: str,
    message_id: str,
    token_counts: dict | None = None,
) -> AsyncIterator[dict]:
    """Run a MAF Workflow in streaming mode.

    Stub for Phase 7 — falls back to agent streaming.  Will be upgraded
    when workflow streaming is fully implemented.
    """
    from .registry import get_registered

    if skill is None or not skill.maf_target_key:
        raise ValidationError(
            "Workflow execution requires a skill with a maf_target_key"
        )

    target = get_registered(skill.maf_target_key)
    if target is None:
        raise NotFoundError(
            f"No registered workflow for key '{skill.maf_target_key}'. "
            "Register a workflow module in src/agents/workflows/."
        )

    # Stub: attempt workflow.run_stream() if available, else fall back
    if hasattr(target, "run_stream"):
        logger.info(
            "Using workflow.run_stream() for key '%s'", skill.maf_target_key
        )
        # TODO: map workflow stream events to SSE events (Phase 7+)
        # For now, fall back to agent streaming
    else:
        logger.warning(
            "Workflow '%s' has no run_stream(); falling back to agent stream.",
            skill.maf_target_key,
        )

    async for event_dict in _run_agent_stream(
        model=model,
        model_client=model_client,
        system_prompt=system_prompt,
        tools=tools,
        user_message=user_message,
        agent_name=agent_name,
        session_id=session_id,
        message_id=message_id,
        token_counts=token_counts,
    ):
        yield event_dict


# ---------------------------------------------------------------------------
# Streaming helpers
# ---------------------------------------------------------------------------


def _sse_event(
    event: str,
    payload: dict,
    session_id: str | None = None,
    message_id: str | None = None,
) -> dict:
    """Build a standard SSE event dict.

    *session_id* and *message_id* are injected into *payload* if not
    already present (they are set by the caller in most cases).
    """
    if session_id is not None and "session_id" not in payload:
        payload["session_id"] = session_id
    if message_id is not None and "message_id" not in payload:
        payload["message_id"] = message_id
    return {"event": event, "data": json.dumps(payload)}


def _maybe_accumulate_text(event_dict: dict, current: str) -> str:
    """If *event_dict* is a ``token`` event, append its delta to *current*."""
    if event_dict.get("event") != "token":
        return current
    try:
        payload = json.loads(event_dict["data"])
        delta = payload.get("delta", "")
        return current + delta
    except (json.JSONDecodeError, KeyError):
        return current


# ---------------------------------------------------------------------------
# Streaming-specific: think-filter wrapper
# ---------------------------------------------------------------------------


class _ThinkFilter:
    """Per-stream stateful ``<think>`` block filter.

    Feeds one token delta at a time and returns filtered text.  State is
    instance-local — safe for concurrent streams.  Used by
    ``_run_agent_stream`` when ``model.provider == "deepseek"`` and
    ``settings.DEEPSEEK_STRIP_REASONING`` is True.
    """

    _OPEN = "<think"
    _CLOSE = "</think>"

    def __init__(self) -> None:
        self._buffer: str = ""
        self._inside: bool = False

    def feed(self, delta: str) -> str:
        """Push *delta* and return any filtered text available right now."""
        self._buffer += delta
        result: list[str] = []

        while self._buffer:
            if self._inside:
                idx = self._buffer.find(self._CLOSE)
                if idx != -1:
                    self._buffer = self._buffer[idx + len(self._CLOSE):]
                    self._inside = False
                else:
                    self._buffer = ""
                    break
            else:
                idx = self._buffer.find(self._OPEN)
                if idx == -1:
                    result.append(self._buffer)
                    self._buffer = ""
                    break
                else:
                    result.append(self._buffer[:idx])
                    self._buffer = self._buffer[idx + len(self._OPEN):]
                    self._inside = True

        return "".join(result)


def _summarise_tool_result(output: Any) -> str:
    """Create a short human-readable summary of a tool result.

    Truncates long strings to avoid bloating SSE events.
    """
    if output is None:
        return "(no output)"
    text = str(output)
    if len(text) > 200:
        return text[:197] + "..."
    return text


def _exc_to_error_code(exc: Exception) -> str:
    """Map an exception to an SSE error code string."""
    name = type(exc).__name__.lower()
    msg = str(exc).lower()

    if "timeout" in name or "timeout" in msg:
        return "model_timeout"
    if "auth" in name or "jwt" in name or "unauthorized" in msg:
        return "auth_error"
    if "tool" in name:
        return "tool_error"
    if "max" in name and "step" in name:
        return "max_steps_exceeded"
    if "invalid" in name or "output" in name or "parse" in name:
        return "invalid_output"
    return "internal_error"


# =============================================================================
# Phase 8 — Branch-aware helpers
# =============================================================================


async def _get_next_branch_index(
    db: AsyncSession,
    session_id: str,
    parent_message_id: str,
) -> int:
    """Return the next available branch index for messages under a parent.

    Queries ``MAX(branch_index) + 1`` for messages where
    ``session_id`` and ``parent_message_id`` match.  Returns 0 if the
    parent has no existing children.
    """
    from sqlalchemy import func as sa_func

    result = await db.execute(
        select(sa_func.max(Message.branch_index)).where(
            Message.session_id == session_id,
            Message.parent_message_id == parent_message_id,
        )
    )
    max_idx = result.scalar()
    if max_idx is None:
        return 0
    return max_idx + 1


async def run_agent_assistant_only(
    session_data: dict,
    user_message_text: str,
    user_message_id: str,
    db: AsyncSession,
    current_user: User,
    assistant_parent_message_id: str,
    assistant_branch_index: int,
) -> tuple[str, str]:
    """Run the agent and persist ONLY an assistant message (no user message).

    Used by the regenerate endpoint — the parent user message already
    exists, and we only need a new assistant response branched from it.

    Args:
        session_data: Unified session dict (from DB or Redis).
        user_message_text: The original user message text to re-run.
        user_message_id: ID of the existing parent user message.
        db: Active async DB session.
        current_user: The authenticated user.
        assistant_parent_message_id: The parent message ID to link the
            new assistant message to (typically *user_message_id*).
        assistant_branch_index: The branch index for this assistant
            message.

    Returns:
        A tuple of (assistant response text, assistant message ID).
    """
    tenant_id = current_user.tenant_id
    session_id = session_data["id"]
    is_temporary = session_data.get("is_temporary", False)

    # ---- 1-6. Resolve session config ------------------------------------
    cfg = await _resolve_session_config(db, session_data, tenant_id, current_user)

    # ---- 7. Run agent or workflow ----------------------------------------
    raw_response: str

    try:
        if cfg.execution_type == "workflow":
            raw_response, tokens_in, tokens_out = await _run_workflow(
                model=cfg.model,
                skill=cfg.skill,
                model_client=cfg.model_client,
                system_prompt=cfg.system_prompt,
                tools=cfg.active_tool_callables,
                user_message=user_message_text,
                agent_name=cfg.agent_name,
            )
        else:
            raw_response, tokens_in, tokens_out = await _run_agent(
                model=cfg.model,
                model_client=cfg.model_client,
                system_prompt=cfg.system_prompt,
                tools=cfg.active_tool_callables,
                user_message=user_message_text,
                agent_name=cfg.agent_name,
            )
    except Exception as exc:
        logger.error("Agent run (assistant-only) failed: %s", exc)
        raise ValidationError(
            f"Agent execution failed: {exc}"
        ) from exc

    # ---- 8. Stabilise DeepSeek output -----------------------------------
    if cfg.model.provider.lower() == "deepseek" and settings.DEEPSEEK_STRIP_REASONING:
        from .stabilizer import stabilize_text
        raw_response = stabilize_text(raw_response)

    # ---- 9. Persist ONLY the assistant message --------------------------
    assistant_msg_content = [{"type": "text", "text": raw_response}]
    assistant_msg_id = str(uuid.uuid4())

    if is_temporary:
        await append_temp_message(
            session_id,
            {
                "id": assistant_msg_id,
                "sender": "assistant",
                "content": assistant_msg_content,
                "model_id": cfg.model.id,
                "parent_message_id": assistant_parent_message_id,
                "branch_index": assistant_branch_index,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    else:
        assistant_msg = Message(
            id=assistant_msg_id,
            session_id=session_id,
            sender="assistant",
            content=assistant_msg_content,
            model_id=cfg.model.id,
            parent_message_id=assistant_parent_message_id,
            branch_index=assistant_branch_index,
        )
        db.add(assistant_msg)
        await db.commit()

    # ---- 10. Write usage log --------------------------------------------
    try:
        await write_usage_log(
            db,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            model_id=cfg.model.id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
    except Exception:
        logger.exception("Failed to write usage log (assistant-only)")

    return raw_response, assistant_msg_id


# ---------------------------------------------------------------------------
# Phase 9 — Token extraction helper
# ---------------------------------------------------------------------------


def _extract_token_counts(result: Any) -> tuple[int, int]:
    """Best-effort extraction of token counts from a MAF agent response.

    Returns:
        A tuple of (tokens_in, tokens_out), defaulting to (0, 0).
    """
    try:
        usage = getattr(result, "usage", None)
        if usage:
            tokens_in = getattr(usage, "input_tokens", 0) or 0
            tokens_out = getattr(usage, "output_tokens", 0) or 0
            return tokens_in, tokens_out
    except Exception:
        pass
    return 0, 0
