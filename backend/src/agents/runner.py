# =============================================================================
# PH Agent Hub — Agent Runner
# =============================================================================
# Per-request MAF agent assembly and execution.
#
# Primary entry point: ``run_agent()``
#
# Resolution chain (model):
#   session.selected_model_id → skill.default_model_id
#   → template.default_model_id → ValidationError
#
# System prompt construction:
#   template.system_prompt + "\\n\\n---\\n\\n" + prompt.content (when both exist)
# =============================================================================

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.exceptions import ValidationError, NotFoundError
from ..core.redis import append_temp_message, get_temp_session
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

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def run_agent(
    session_data: dict,
    user_message: str,
    db: AsyncSession,
    current_user: User,
) -> str:
    """Assemble and run a MAF agent for a single user message.

    Args:
        session_data: Unified session dict (from DB or Redis).
        user_message: The text the user sent.
        db: Active async DB session.
        current_user: The authenticated user.

    Returns:
        The assistant's response text.
    """
    tenant_id = current_user.tenant_id
    session_id = session_data["id"]
    is_temporary = session_data.get("is_temporary", False)

    # ---- 1. Resolve model ------------------------------------------------
    model = await _resolve_model(db, session_data)
    model_client = get_chat_client(model)

    # ---- 2. Build system prompt ------------------------------------------
    system_prompt = await _build_system_prompt(db, session_data)

    # ---- 3. Resolve skill ------------------------------------------------
    skill = await _resolve_skill(db, session_data)

    # ---- 4. Resolve active tools -----------------------------------------
    active_tool_callables = await _resolve_tool_callables(
        db, session_data, tenant_id
    )

    # ---- 5. Determine execution type and name ----------------------------
    execution_type = skill.execution_type if skill else "agent"
    agent_name = skill.title if skill else "assistant"

    # ---- 6. Apply DeepSeek middleware ------------------------------------
    if model.provider.lower() == "deepseek":
        from .deepseek_patch import apply_deepseek_patches
        apply_deepseek_patches()

    # ---- 7. Run agent or workflow ----------------------------------------
    raw_response: str

    try:
        if execution_type == "workflow":
            raw_response = await _run_workflow(
                model=model,
                skill=skill,
                model_client=model_client,
                system_prompt=system_prompt,
                tools=active_tool_callables,
                user_message=user_message,
                agent_name=agent_name,
            )
        else:
            raw_response = await _run_agent(
                model=model,
                model_client=model_client,
                system_prompt=system_prompt,
                tools=active_tool_callables,
                user_message=user_message,
                agent_name=agent_name,
            )
    except Exception as exc:
        logger.error("Agent run failed: %s", exc)
        raise ValidationError(
            f"Agent execution failed: {exc}"
        ) from exc

    # ---- 8. Stabilise DeepSeek output -----------------------------------
    if model.provider.lower() == "deepseek" and settings.DEEPSEEK_STRIP_REASONING:
        from .stabilizer import stabilize_text
        raw_response = stabilize_text(raw_response)

    # ---- 9. Persist messages --------------------------------------------
    await _persist_messages(
        db=db,
        session_id=session_id,
        is_temporary=is_temporary,
        user_message=user_message,
        assistant_response=raw_response,
        model_id=model.id,
    )

    return raw_response


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------


async def _resolve_model(
    db: AsyncSession, session_data: dict
) -> Model:
    """Resolve the model client following the fallback chain."""
    # 1. session.selected_model_id
    model_id = session_data.get("selected_model_id")
    if model_id:
        result = await db.execute(select(Model).where(Model.id == model_id))
        model = result.scalar_one_or_none()
        if model:
            return model

    # 2. skill.default_model_id
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

    # 3. template.default_model_id
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

    raise ValidationError(
        "No model configured. Please select a model for this session, "
        "or configure a default model on the skill or template."
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
) -> str:
    """Run a simple MAF Agent."""
    from agent_framework import Agent

    agent = Agent(
        client=model_client,
        name=agent_name,
        instructions=system_prompt,
        tools=tools,
    )

    result = await agent.run(user_message)

    # result could be a string or a structured object
    if isinstance(result, str):
        return result

    # MAF may return an object with a .final_output or .content attribute
    if hasattr(result, "final_output"):
        return str(result.final_output)
    if hasattr(result, "content"):
        return str(result.content)

    return str(result)


async def _run_workflow(
    model: Model,
    skill: Skill,
    model_client: Any,
    system_prompt: str,
    tools: list,
    user_message: str,
    agent_name: str,
) -> str:
    """Run a MAF Workflow via the registry."""
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


async def _persist_messages(
    db: AsyncSession,
    session_id: str,
    is_temporary: bool,
    user_message: str,
    assistant_response: str,
    model_id: str,
) -> None:
    """Persist the user message and assistant response."""
    user_msg_content = [{"type": "text", "text": user_message}]
    assistant_msg_content = [{"type": "text", "text": assistant_response}]

    if is_temporary:
        # Store in Redis
        await append_temp_message(
            session_id,
            {
                "id": str(uuid.uuid4()),
                "sender": "user",
                "content": user_msg_content,
                "branch_index": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        await append_temp_message(
            session_id,
            {
                "id": str(uuid.uuid4()),
                "sender": "assistant",
                "content": assistant_msg_content,
                "model_id": model_id,
                "branch_index": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    else:
        # Store in MariaDB
        user_msg = Message(
            session_id=session_id,
            sender="user",
            content=user_msg_content,
            branch_index=0,
        )
        db.add(user_msg)
        await db.flush()

        assistant_msg = Message(
            session_id=session_id,
            sender="assistant",
            content=assistant_msg_content,
            model_id=model_id,
            branch_index=0,
        )
        db.add(assistant_msg)
        await db.commit()
