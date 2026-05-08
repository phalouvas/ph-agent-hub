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
    get_temp_messages,
    get_temp_session,
)
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
    thinking_enabled: bool


async def _resolve_session_config(
    db: AsyncSession,
    session_data: dict,
    tenant_id: str,
    user: User | None = None,
    file_ids: list[str] | None = None,
) -> SessionConfig:
    """Resolve model, system prompt, skill, tools, execution type, and agent name.

    Centralises the resolution chain shared by ``run_agent()``,
    ``run_agent_stream()``, and ``run_agent_assistant_only()``.
    """
    # 1. Resolve model
    model = await _resolve_model(db, session_data, user)

    # 2. Build system prompt
    system_prompt = await _build_system_prompt(db, session_data)

    # 3. Resolve skill
    skill = await _resolve_skill(db, session_data)

    # 4. Resolve active tools
    active_tool_callables = await _resolve_tool_callables(
        db, session_data, tenant_id, file_ids=file_ids
    )

    # 5. Determine execution type and name
    execution_type = skill.execution_type if skill else "agent"
    # Normalize: workflow_based → workflow, prompt_based → agent
    if execution_type == "workflow_based":
        execution_type = "workflow"
    if execution_type == "prompt_based":
        execution_type = "agent"
    agent_name = skill.title if skill else "assistant"

    # 6. Resolve thinking_enabled: session override > model default
    thinking_enabled = session_data.get("thinking_enabled")
    if thinking_enabled is None:
        thinking_enabled = getattr(model, "thinking_enabled", False)

    # Rebuild model_client with thinking_enabled
    model_client = get_chat_client(model, thinking_enabled=thinking_enabled)

    return SessionConfig(
        model=model,
        model_client=model_client,
        system_prompt=system_prompt,
        skill=skill,
        active_tool_callables=active_tool_callables,
        execution_type=execution_type,
        agent_name=agent_name,
        thinking_enabled=thinking_enabled,
    )


# ---------------------------------------------------------------------------
# Message summarization (Issue #29)
# ---------------------------------------------------------------------------

# Conservative estimate: ~4 characters per token. Works across all
# model families without requiring provider-specific tokenizers.
CHARS_PER_TOKEN_ESTIMATE = 4

# Fraction of context_length at which auto-summarization triggers.
SUMMARIZE_THRESHOLD = 0.75

# Number of most recent user/assistant message *pairs* to keep intact
# when summarizing. Older messages are compressed into a summary.
KEEP_RECENT_PAIRS = 3

# Maximum summary length in characters (to keep the summary itself
# from consuming too much context).
MAX_SUMMARY_CHARS = 2000


def _estimate_tokens(text: str) -> int:
    """Estimate token count from character length.

    Uses a conservative 4 chars/token ratio that slightly over-estimates
    for most models, ensuring we trigger summarization before truly
    running out of context.
    """
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN_ESTIMATE)


def _extract_message_text(content: list | None) -> str:
    """Extract readable text from a message's JSON content array.

    Handles the structured content format used by _persist_assistant_message.
    """
    if not content or not isinstance(content, list):
        return ""

    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type", "")
        if item_type == "text":
            text = item.get("text", "")
            if text:
                parts.append(text)
        elif item_type == "function_call":
            name = item.get("name", "unknown")
            parts.append(f"[Used tool: {name}]")
        elif item_type == "function_result":
            name = item.get("name", "unknown")
            output = item.get("output", "")
            if isinstance(output, str) and output:
                # Truncate tool output in history
                truncated = output[:300] + "..." if len(output) > 300 else output
                parts.append(f"[Tool result from {name}: {truncated}]")

    return "\n".join(parts)


def _msg_get(msg, attr: str, default=None):
    """Read an attribute from an ORM object or a key from a dict.

    Handles both Message ORM objects (DB) and message dicts (Redis).
    """
    if isinstance(msg, dict):
        return msg.get(attr, default)
    return getattr(msg, attr, default)


def _format_conversation_history(messages: list) -> str:
    """Format a list of message dicts/ORMs into a readable history string.

    Used to inject past conversation into the model context.
    Summarized messages are skipped (replaced by the summary system message).
    """
    if not messages:
        return ""

    lines: list[str] = ["[Previous conversation]"]

    for msg in messages:
        sender = _msg_get(msg, "sender", "")
        content = _msg_get(msg, "content")
        summarized = _msg_get(msg, "summarized", False)

        if summarized:
            continue  # Skip messages that have been compressed into a summary

        text = _extract_message_text(content)
        if not text:
            continue

        if sender == "user":
            lines.append(f"User: {text}")
        elif sender == "assistant":
            lines.append(f"Assistant: {text}")
        elif sender == "system":
            lines.append(f"[Summary of earlier conversation]\n{text}")

    if len(lines) == 1:
        return ""  # Only the header, no actual messages

    return "\n\n".join(lines)


def _build_history_string(
    messages: list,
    context_length: int | None,
) -> str:
    """Build conversation history for inclusion in the model context.

    Respects a token budget to avoid the history itself consuming too
    much of the context window. Includes up to 60% of context_length
    for history, leaving room for system prompt, tools, and the new
    user message + response.
    """
    if not messages:
        return ""

    full_history = _format_conversation_history(messages)
    if not full_history:
        return ""

    # Budget: 60% of context_length for history
    if context_length:
        history_budget_tokens = int(context_length * 0.6)
        history_budget_chars = history_budget_tokens * CHARS_PER_TOKEN_ESTIMATE
    else:
        history_budget_chars = 8000 * CHARS_PER_TOKEN_ESTIMATE  # ~32K chars default

    if len(full_history) <= history_budget_chars:
        return full_history

    # Truncate from the beginning (oldest messages first)
    # Keep the last history_budget_chars characters
    truncated = "...\n(earlier conversation omitted)\n\n" + full_history[-history_budget_chars:]
    return truncated


async def _get_messages_for_session(
    db: AsyncSession,
    session_id: str,
    is_temporary: bool,
) -> list:
    """Retrieve ordered, non-deleted messages for a session.

    Returns a list of Message ORM objects (DB) or message dicts (Redis).
    """
    if is_temporary:
        raw = await get_temp_messages(session_id)
        return raw or []
    else:
        result = await db.execute(
            select(Message)
            .where(
                Message.session_id == session_id,
                Message.is_deleted == False,  # noqa: E712
            )
            .order_by(Message.created_at)
        )
        return list(result.scalars().all())


async def _generate_summary(
    model: Model,
    model_client: Any,
    messages_to_summarize: list,
) -> str | None:
    """Use the configured model to generate a concise summary of past messages.

    Detects existing summary system messages in the input and merges them
    into a single consolidated summary, avoiding summary accumulation over
    very long conversations.

    Creates a fresh non-thinking client for the summarization call.
    Returns None on failure (summarization is best-effort).
    """
    if not messages_to_summarize:
        return None

    # Separate existing summary system messages from regular messages.
    # Existing summaries should be merged into the new one rather than
    # treated as raw conversation, which would bloat the prompt.
    existing_summaries: list[str] = []
    regular_messages: list = []

    for msg in messages_to_summarize:
        sender = _msg_get(msg, "sender", "")
        if sender == "system":
            # This is a previous summary — extract its text
            content = _msg_get(msg, "content")
            text = _extract_message_text(content)
            if text:
                existing_summaries.append(text)
        else:
            regular_messages.append(msg)

    # Build the conversation text for the regular (non-summary) messages
    conversation_text = _format_conversation_history(regular_messages)

    # Build the full prompt: merge existing summaries with new content
    if existing_summaries:
        # There are previous summaries — ask the LLM to merge them
        summaries_block = "\n".join(
            f"- {s}" for s in existing_summaries
        )
        if conversation_text:
            summary_prompt = (
                "You are maintaining a running conversation summary. "
                "Below are one or more EXISTING summaries of earlier parts "
                "of the conversation, followed by newer messages. "
                "Merge everything into a SINGLE concise summary.\n\n"
                "=== EXISTING SUMMARIES (merge these into your response) ===\n"
                f"{summaries_block}\n\n"
                "=== NEWER CONVERSATION ===\n"
                f"{conversation_text}\n\n"
                "Produce ONE consolidated summary. Focus on key topics, "
                "decisions, important facts, and pending questions. "
                "Write in plain English, no more than 200 words. "
                "Do NOT use meta-phrases like 'The conversation covered' — "
                "just state the facts directly as a compact record."
            )
        else:
            # Only summaries, no regular messages — merge them directly
            summary_prompt = (
                "Below are multiple conversation summaries. "
                "Merge them into a SINGLE concise summary.\n\n"
                "=== SUMMARIES TO MERGE ===\n"
                f"{summaries_block}\n\n"
                "Produce ONE consolidated summary. Focus on key topics, "
                "decisions, important facts, and pending questions. "
                "Write in plain English, no more than 200 words. "
                "Do NOT use meta-phrases — just state the facts directly."
            )
    elif conversation_text:
        # No existing summaries — standard summarization
        summary_prompt = (
            "Summarize the following conversation concisely. "
            "Focus on key topics discussed, decisions made, important facts shared, "
            "and any pending questions or action items. "
            "Write in plain English, no more than 200 words. "
            "Do NOT include phrases like 'The conversation covered' or 'The user and assistant discussed' — "
            "just state the facts directly as a compact record.\n\n"
            f"{conversation_text}"
        )
    else:
        return None

    messages_payload = [
        {"role": "user", "content": summary_prompt},
    ]

    try:
        # Create a fresh client (non-thinking mode for simpler output)
        from ..models.base import get_chat_client

        fresh_client = get_chat_client(model, thinking_enabled=False)
        raw_client = getattr(fresh_client, "client", None)
        if raw_client is None:
            logger.warning("No client attribute on fresh model_client, skipping summarization")
            return None

        model_name = getattr(fresh_client, "model", model.model_id)
        response = await raw_client.chat.completions.create(
            model=model_name,
            messages=messages_payload,
            max_tokens=300,
            temperature=0.3,  # Low temp for factual summary
        )
        summary = response.choices[0].message.content if response.choices else ""
        summary = (summary or "").strip()

        if summary and len(summary) > MAX_SUMMARY_CHARS:
            summary = summary[:MAX_SUMMARY_CHARS] + "..."

        return summary if summary else None

    except Exception:
        logger.exception("Failed to generate conversation summary")
        return None


async def _maybe_summarize_and_build_context(
    db: AsyncSession,
    session_data: dict,
    cfg: "SessionConfig",
    user_message: str,
) -> tuple[str, dict | None]:
    """Check if summarization is needed and build the contextualized message.

    Returns:
        A tuple of (contextualized_message, summary_info_or_None).
        summary_info is a dict with keys: summary_text, summarized_count,
        tokens_saved — used for the SSE summarized event.
    """
    session_id = session_data["id"]
    is_temporary = session_data.get("is_temporary", False)
    context_length = getattr(cfg.model, "context_length", None)

    # Get all messages
    all_messages = await _get_messages_for_session(db, session_id, is_temporary)

    if not all_messages:
        return user_message, None

    # Estimate total tokens of the full context
    system_prompt_tokens = _estimate_tokens(cfg.system_prompt or "")
    user_msg_tokens = _estimate_tokens(user_message)
    history_tokens = sum(
        _estimate_tokens(_extract_message_text(
            _msg_get(m, "content")
        ))
        for m in all_messages
        if not _msg_get(m, "summarized", False)
    )
    total_estimated = system_prompt_tokens + user_msg_tokens + history_tokens

    # Determine threshold
    threshold_tokens = int((context_length or 8192) * SUMMARIZE_THRESHOLD)

    summary_info: dict | None = None

    if total_estimated > threshold_tokens and context_length:
        # Need to summarize. Keep the last KEEP_RECENT_PAIRS pairs intact.
        # Messages are in chronological order; find the cutoff point.
        non_summarized = [
            m for m in all_messages
            if not _msg_get(m, "summarized", False)
        ]

        # Count user+assistant pairs from the end
        pair_count = 0
        cutoff_idx = len(non_summarized)
        for i in range(len(non_summarized) - 1, -1, -1):
            msg = non_summarized[i]
            sender = _msg_get(msg, "sender", "")
            if sender == "user":
                pair_count += 1
                if pair_count >= KEEP_RECENT_PAIRS:
                    cutoff_idx = i
                    break

        messages_to_summarize = non_summarized[:cutoff_idx]

        if messages_to_summarize:
            logger.info(
                "Auto-summarizing %d messages for session %s "
                "(estimated %d tokens, threshold %d)",
                len(messages_to_summarize), session_id,
                total_estimated, threshold_tokens,
            )

            summary_text = await _generate_summary(
                model=cfg.model,
                model_client=cfg.model_client,
                messages_to_summarize=messages_to_summarize,
            )

            if summary_text:
                # Mark messages as summarized
                if is_temporary:
                    # For temp sessions, update the Redis messages
                    all_raw = await get_temp_messages(session_id)
                    for raw_msg in all_raw:
                        raw_id = raw_msg.get("id", "")
                        for to_mark in messages_to_summarize:
                            mark_id = _msg_get(to_mark, "id", "")
                            if raw_id == mark_id:
                                raw_msg["summarized"] = True
                    # Re-store updated messages with TTL refresh
                    from ..core.redis import get_redis
                    r = await get_redis()
                    import json as _json
                    msg_key = f"session:tmp:{session_id}:messages"
                    session_key = f"session:tmp:{session_id}"
                    ttl = await r.ttl(session_key)
                    if ttl and ttl > 0:
                        await r.setex(msg_key, ttl, _json.dumps(all_raw))
                    else:
                        await r.setex(msg_key, settings.TEMPORARY_SESSION_TTL_SECONDS, _json.dumps(all_raw))
                else:
                    # For DB sessions, update the summarized flag
                    for msg in messages_to_summarize:
                        if hasattr(msg, "summarized"):
                            msg.summarized = True
                    await db.commit()

                # Store the summary as a system message
                summary_content = [{"type": "text", "text": summary_text}]
                await _persist_system_message(
                    db=db,
                    session_id=session_id,
                    is_temporary=is_temporary,
                    content=summary_content,
                )

                # Calculate tokens saved
                old_tokens = sum(
                    _estimate_tokens(_extract_message_text(
                        _msg_get(m, "content")
                    ))
                    for m in messages_to_summarize
                )
                new_tokens = _estimate_tokens(summary_text)
                tokens_saved = max(0, old_tokens - new_tokens)

                summary_info = {
                    "summary_text": summary_text,
                    "summarized_count": len(messages_to_summarize),
                    "tokens_saved": tokens_saved,
                }

                logger.info(
                    "Summarization complete for session %s: "
                    "%d messages compressed, ~%d tokens saved",
                    session_id, len(messages_to_summarize), tokens_saved,
                )

    # Build the contextualized message with history
    # Re-fetch messages (summarization may have changed the list)
    current_messages = await _get_messages_for_session(db, session_id, is_temporary)
    history_str = _build_history_string(current_messages, context_length)

    if history_str:
        contextualized = f"{history_str}\n\n---\n\nCurrent message: {user_message}"
        return contextualized, summary_info

    return user_message, summary_info


async def _persist_system_message(
    db: AsyncSession,
    session_id: str,
    is_temporary: bool,
    content: list[dict],
) -> str:
    """Persist a system message (used for conversation summaries).

    Returns the message ID.
    """
    msg_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    if is_temporary:
        await append_temp_message(
            session_id,
            {
                "id": msg_id,
                "sender": "system",
                "content": content,
                "parent_message_id": None,
                "branch_index": 0,
                "created_at": now.isoformat(),
            },
        )
    else:
        msg = Message(
            id=msg_id,
            session_id=session_id,
            sender="system",
            content=content,
            parent_message_id=None,
            branch_index=0,
            created_at=now,
        )
        db.add(msg)
        await db.commit()

    return msg_id


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
    file_ids: list[str] | None = None,
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
        file_ids: Optional list of FileUpload IDs to link to the user message.

    Returns:
        A tuple of (assistant response text, assistant message ID).
    """
    tenant_id = current_user.tenant_id
    session_id = session_data["id"]
    is_temporary = session_data.get("is_temporary", False)

    # ---- 1-6. Resolve session config ------------------------------------
    cfg = await _resolve_session_config(db, session_data, tenant_id, current_user, file_ids=file_ids)

    # ---- Build contextualized message (history + auto-summarization) ----
    contextualized_message, _ = await _maybe_summarize_and_build_context(
        db=db,
        session_data=session_data,
        cfg=cfg,
        user_message=user_message,
    )

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
                user_message=contextualized_message,
                agent_name=cfg.agent_name,
            )
        else:
            raw_response, tokens_in, tokens_out = await _run_agent(
                model=cfg.model,
                model_client=cfg.model_client,
                system_prompt=cfg.system_prompt,
                tools=cfg.active_tool_callables,
                user_message=contextualized_message,
                agent_name=cfg.agent_name,
            )
    except Exception as exc:
        logger.error("Agent run failed: %s", exc)
        raise ValidationError(
            f"Agent execution failed: {exc}"
        ) from exc

    # ---- 8. Persist messages --------------------------------------------
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

    # ---- 9. Link file uploads to the user message ------------------------
    if file_ids:
        from ..services import upload_service as _upload_svc

        await _upload_svc.link_uploads_to_message(
            db=db,
            file_ids=file_ids,
            message_id=_user_msg_id,
            user_id=current_user.id,
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
    file_ids: list[str] | None = None,
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
        tool_callables = await _build_tool_callables(db, tool, tenant_id, file_ids=file_ids)
        callables.extend(tool_callables)

    return callables


async def _build_tool_callables(
    db: AsyncSession,
    tool: Tool,
    tenant_id: str,
    file_ids: list[str] | None = None,
) -> list:
    """Dispatch on tool.type to the appropriate factory."""
    if tool.type == "erpnext":
        return await _build_erpnext_callables(db, tool, tenant_id, file_ids=file_ids)
    elif tool.type == "membrane":
        from ..tools.membrane import build_membrane_tools
        return build_membrane_tools(tool.config or {})
    elif tool.type == "custom":
        # Stub for Phase 6
        return []
    elif tool.type == "datetime":
        from ..tools.datetime import build_datetime_tools
        return build_datetime_tools(tool.config or {})
    elif tool.type == "web_search":
        from ..tools.web_search import build_web_search_tools
        return build_web_search_tools(tool.config or {})
    else:
        logger.warning("Unknown tool type '%s' for tool %s", tool.type, tool.id)
        return []


async def _build_erpnext_callables(
    db: AsyncSession,
    tool: Tool,
    tenant_id: str,
    file_ids: list[str] | None = None,
) -> list:
    """Build ERPNext tool callables for a given Tool record.

    Reads credentials directly from ``tool.config`` JSON.
    If ``file_ids`` are provided, queries FileUpload records and passes
    them to the ERPNext factory so the ``upload_file`` tool can access
    file binaries from MinIO.
    """
    from ..tools.erpnext import build_erpnext_tools

    config = tool.config or {}
    base_url = config.get("base_url")
    api_key = config.get("api_key")
    api_secret = config.get("api_secret")

    if not all([base_url, api_key, api_secret]):
        raise NotFoundError(
            f"ERPNext tool '{tool.name}' is missing required config fields. "
            "Set base_url, api_key, and api_secret in the tool config."
        )

    # Resolve file infos if file_ids were provided
    file_infos: list[dict] | None = None
    if file_ids:
        from ..db.orm.file_uploads import FileUpload
        from sqlalchemy import select as sa_select
        result = await db.execute(
            sa_select(FileUpload).where(
                FileUpload.id.in_(file_ids),
                FileUpload.tenant_id == tenant_id,
            )
        )
        uploads = list(result.scalars().all())
        if uploads:
            file_infos = [
                {
                    "id": u.id,
                    "storage_key": u.storage_key,
                    "bucket": u.bucket,
                    "original_filename": u.original_filename,
                    "content_type": u.content_type,
                }
                for u in uploads
            ]

    return build_erpnext_tools(
        base_url=base_url,
        api_key=api_key,
        api_secret=api_secret,
        file_infos=file_infos,
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
    tool_events: list[dict] | None = None,
) -> str:
    """Persist just the assistant message, returning its ID."""
    content: list[dict] = []

    # Build content array: tool events interleaved before the final text
    for evt in (tool_events or []):
        content.append(evt)

    # Always append the final text response
    if assistant_response.strip():
        content.append({"type": "text", "text": assistant_response})
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


async def run_agent_stream(
    session_data: dict,
    user_message: str,
    db: AsyncSession,
    current_user: User,
    message_id: str,
    file_ids: list[str] | None = None,
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
        file_ids: Optional list of FileUpload IDs to link to the user message.

    Yields:
        Dicts with ``event`` and ``data`` keys suitable for
        ``EventSourceResponse``.
    """
    tenant_id = current_user.tenant_id
    session_id = session_data["id"]
    is_temporary = session_data.get("is_temporary", False)

    accumulated_text: str = ""
    accumulated_tool_events: list[dict] = []
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

    # Link file uploads to the user message
    if file_ids:
        from ..services import upload_service as _upload_svc

        await _upload_svc.link_uploads_to_message(
            db=db,
            file_ids=file_ids,
            message_id=user_msg_id,
            user_id=current_user.id,
        )

    try:
        # ---- 1-6. Resolve session config --------------------------------
        cfg = await _resolve_session_config(db, session_data, tenant_id, current_user, file_ids=file_ids)

        # ---- Build contextualized message (history + auto-summarization) --
        contextualized_message, summary_info = await _maybe_summarize_and_build_context(
            db=db,
            session_data=session_data,
            cfg=cfg,
            user_message=user_message,
        )

        # Emit summarized event if auto-summarization happened
        if summary_info:
            yield {
                "event": "summarized",
                "data": json.dumps({
                    "session_id": session_id,
                    "message_id": message_id,
                    "summary": summary_info["summary_text"],
                    "summarized_message_count": summary_info["summarized_count"],
                    "tokens_saved": summary_info["tokens_saved"],
                }),
            }

        # ---- 7. Run agent or workflow (streaming) ------------------------
        if cfg.execution_type == "workflow":
            stream = _run_workflow_stream(
                model=cfg.model,
                skill=cfg.skill,
                model_client=cfg.model_client,
                system_prompt=cfg.system_prompt,
                tools=cfg.active_tool_callables,
                user_message=contextualized_message,
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
                user_message=contextualized_message,
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
            # Accumulate tool events for persistence
            accumulated_tool_events = _maybe_accumulate_tool_events(
                event_dict, accumulated_tool_events
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

    # ---- 8. Extract token counts from stream final response -------------
    tokens_in, tokens_out = _stream_token_info.get("in", 0), _stream_token_info.get("out", 0)

    # ---- 9. Persist assistant message ------------------------------------
    await _persist_assistant_message(
        db=db,
        session_id=session_id,
        is_temporary=is_temporary,
        assistant_response=accumulated_text,
        model_id=cfg.model.id,
        parent_message_id=user_msg_id,
        tool_events=accumulated_tool_events,
    )

    # ---- 10. Write usage log ---------------------------------------------
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

    # ---- 11. Emit message_complete ---------------------------------------
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

    # ---- 12. Generate follow-up questions (if enabled) --------------------
    if getattr(cfg.model, "follow_up_questions_enabled", False):
        try:
            questions = await _generate_follow_up_questions(
                model=cfg.model,
                system_prompt=cfg.system_prompt,
                user_message=user_message,
                assistant_response=accumulated_text,
            )
            if questions:
                yield {
                    "event": "follow_up_questions",
                    "data": json.dumps({
                        "session_id": session_id,
                        "message_id": message_id,
                        "questions": questions,
                    }),
                }
        except Exception:
            logger.exception(
                "Failed to generate follow-up questions for session %s",
                session_id,
            )


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
    """Run a MAF Agent in streaming mode, yielding SSE event dicts.

    .. note::

        MAF streams tool-call arguments incrementally (character by
        character).  We aggregate partial *function_call* updates by
        ``call_id`` and only emit a single ``tool_start`` SSE event
        once the call is complete (when *function_result* arrives).
    """
    from agent_framework import Agent

    agent = Agent(
        client=model_client,
        name=agent_name,
        instructions=system_prompt,
        tools=tools,
    )

    response_stream = agent.run(user_message, stream=True)

    step_index = 0
    # Aggregate streaming tool calls: call_id -> {name, args_str}
    pending_calls: dict[str, dict] = {}

    async for update in response_stream:
        # Check each content item in the update
        for content in update.contents:
            content_type = getattr(content, "type", None)

            if content_type == "text":
                delta = getattr(content, "text", "")
                if delta:
                    yield _sse_event("token", {
                        "delta": delta,
                    }, session_id=session_id, message_id=message_id)
            elif content_type == "text_reasoning":
                delta = getattr(content, "text", "")
                if delta:
                    yield _sse_event("reasoning_token", {
                        "delta": delta,
                    }, session_id=session_id, message_id=message_id)
            elif content_type in ("function_call", "tool_call"):
                _handle_streaming_function_call(content, pending_calls)
            elif content_type in ("function_result", "tool_result"):
                tool_call_id = getattr(content, "call_id", None) or ""
                tool_name = getattr(content, "name", "unknown")
                output = getattr(content, "output", None) or getattr(content, "result", None)
                success = True  # MAF surfaces errors via separate content types
                result_summary = _summarise_tool_result(output)

                # Resolve the final tool name and arguments from pending calls
                resolved_args = None
                if tool_call_id and tool_call_id in pending_calls:
                    pending = pending_calls.pop(tool_call_id)
                    if pending.get("name"):
                        tool_name = pending["name"]
                    resolved_args = _resolve_tool_arguments(
                        pending.get("args_str", ""), output
                    )

                # Yield a single consolidated tool_start event
                yield _sse_event("tool_start", {
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "arguments": resolved_args,
                }, session_id=session_id, message_id=message_id)

                # Yield the tool_result event
                yield _sse_event("tool_result", {
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "success": success,
                    "result_summary": result_summary,
                    "output": output,
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


def _maybe_accumulate_tool_events(
    event_dict: dict, current: list[dict]
) -> list[dict]:
    """If *event_dict* is a tool_start or tool_result event,
    append it to *current* for later persistence."""
    event_name = event_dict.get("event", "")
    if event_name not in ("tool_start", "tool_result"):
        return current
    try:
        payload = json.loads(event_dict["data"])
    except (json.JSONDecodeError, KeyError):
        return current

    if event_name == "tool_start":
        return current + [{
            "type": "function_call",
            "name": payload.get("tool_name", "unknown"),
            "arguments": payload.get("arguments", {}),
            "id": payload.get("tool_call_id", ""),
        }]
    else:
        # tool_result
        return current + [{
            "type": "function_result",
            "name": payload.get("tool_name", "unknown"),
            "output": _format_tool_output_for_storage(payload.get("output")),
            "is_error": not payload.get("success", True),
        }]


def _format_tool_output_for_storage(output: Any) -> str | None:
    """Format a tool output value for JSON storage in message content.

    Returns a string representation suitable for display.  Limits the
    size of very large outputs to avoid bloated message content.
    """
    if output is None:
        return None
    if isinstance(output, str):
        if len(output) > 4000:
            return output[:4000] + "\n...(truncated)"
        return output
    try:
        serialized = json.dumps(output, default=str)
    except (TypeError, ValueError):
        serialized = str(output)
    if len(serialized) > 4000:
        serialized = serialized[:4000] + "\n...(truncated)"
    return serialized


# ---------------------------------------------------------------------------
# Streaming-specific: think-filter wrapper
# ---------------------------------------------------------------------------


def _handle_streaming_function_call(
    content: Any,
    pending_calls: dict[str, dict],
) -> None:
    """Accumulate a streaming *function_call* content into *pending_calls*.

    MAF may yield multiple partial function_call updates for the same
    call_id — the first carries the tool name, subsequent ones carry
    fragments of the JSON arguments string.
    """
    call_id = getattr(content, "call_id", None) or str(uuid.uuid4())
    tool_name = getattr(content, "name", None) or ""
    arguments = getattr(content, "arguments", None)

    if call_id not in pending_calls:
        pending_calls[call_id] = {"name": "", "args_str": ""}

    pending = pending_calls[call_id]

    # Update name if we got a real one
    if tool_name and tool_name != "unknown":
        pending["name"] = tool_name

    # Accumulate argument fragments
    if arguments is not None:
        if isinstance(arguments, str):
            pending["args_str"] = (pending["args_str"] or "") + arguments
        else:
            # Already a dict/list — store directly
            pending["args_str"] = arguments


def _resolve_tool_arguments(
    args_str: Any,
    output: Any,
) -> dict | None:
    """Try to parse accumulated streaming arguments into a dict.

    Returns the parsed arguments dict, or None if parsing fails.
    """
    if args_str is None:
        return None
    if isinstance(args_str, dict):
        return args_str
    if isinstance(args_str, str) and args_str.strip():
        try:
            parsed = json.loads(args_str)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return None


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


# ---------------------------------------------------------------------------
# Follow-up questions generation (Phase 10+)
# ---------------------------------------------------------------------------


async def _generate_follow_up_questions(
    model: Model,
    system_prompt: str,
    user_message: str,
    assistant_response: str,
) -> list[str]:
    """Generate 3 follow-up questions based on the conversation context.

    Creates a fresh non-thinking model client and makes a quick
    non-streaming call. Returns an empty list on failure.
    """
    prompt = (
        "Based on the conversation above, generate exactly 3 concise follow-up "
        "questions that the user might want to ask next. The questions should be "
        "relevant to the topic discussed and help the user explore further.\n\n"
        "Rules:\n"
        "- Return ONLY a JSON array of 3 strings, nothing else.\n"
        "- Each question should be a single sentence, no more than 100 characters.\n"
        "- Do not number the questions.\n"
        '- Example format: ["Question one?", "Question two?", "Question three?"]'
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": assistant_response},
        {"role": "user", "content": prompt},
    ]

    try:
        # Create a fresh client (non-thinking mode for simpler output)
        from ..models.base import get_chat_client

        fresh_client = get_chat_client(model, thinking_enabled=False)

        # Access the underlying OpenAI client via .client property
        raw_client = getattr(fresh_client, "client", None)
        if raw_client is None:
            logger.warning("No client attribute on fresh model_client, skipping follow-up questions")
            return []

        model_name = getattr(fresh_client, "model", model.model_id)
        response = await raw_client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=200,
            temperature=0.7,
        )
        text = response.choices[0].message.content if response.choices else ""

        # Parse the JSON array from the response
        text = (text or "").strip()
        # Remove markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:]) if len(lines) > 1 else text
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        questions = json.loads(text)
        if isinstance(questions, list) and all(isinstance(q, str) for q in questions):
            return questions[:3]

    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Failed to parse follow-up questions: %s", exc)

    return []


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

    # ---- Build contextualized message (history + auto-summarization) ----
    contextualized_message, _ = await _maybe_summarize_and_build_context(
        db=db,
        session_data=session_data,
        cfg=cfg,
        user_message=user_message_text,
    )

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
                user_message=contextualized_message,
                agent_name=cfg.agent_name,
            )
        else:
            raw_response, tokens_in, tokens_out = await _run_agent(
                model=cfg.model,
                model_client=cfg.model_client,
                system_prompt=cfg.system_prompt,
                tools=cfg.active_tool_callables,
                user_message=contextualized_message,
                agent_name=cfg.agent_name,
            )
    except Exception as exc:
        logger.error("Agent run (assistant-only) failed: %s", exc)
        raise ValidationError(
            f"Agent execution failed: {exc}"
        ) from exc

    # ---- 8. Persist ONLY the assistant message --------------------------
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
