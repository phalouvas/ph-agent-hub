# =============================================================================
# PH Agent Hub — Tool Service (CRUD)
# =============================================================================

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import NotFoundError, ValidationError
from ..db.orm.tools import Tool

VALID_TOOL_TYPES = {"erpnext", "membrane", "custom"}


async def list_tools(
    db: AsyncSession, tenant_id: str | None = None
) -> list[Tool]:
    """Return all tools, optionally filtered by tenant_id."""
    stmt = select(Tool)
    if tenant_id is not None:
        stmt = stmt.where(Tool.tenant_id == tenant_id)
    stmt = stmt.order_by(Tool.created_at)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_tool_by_id(db: AsyncSession, tool_id: str) -> Tool | None:
    """Look up a tool by primary key."""
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    return result.scalar_one_or_none()


async def create_tool(
    db: AsyncSession,
    tenant_id: str,
    name: str,
    type: str,
    config: dict | None = None,
    enabled: bool = True,
) -> Tool:
    """Create a new tool. Raises ValidationError if type is invalid."""
    if type not in VALID_TOOL_TYPES:
        raise ValidationError(
            f"Invalid tool type '{type}'. "
            f"Must be one of: {', '.join(sorted(VALID_TOOL_TYPES))}"
        )

    tool = Tool(
        tenant_id=tenant_id,
        name=name,
        type=type,
        config=config,
        enabled=enabled,
    )
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return tool


async def update_tool(db: AsyncSession, tool_id: str, **fields) -> Tool:
    """Update a tool's fields. Raises NotFoundError if missing,
    ValidationError if type is invalid."""
    tool = await get_tool_by_id(db, tool_id)
    if tool is None:
        raise NotFoundError("Tool not found")

    if "type" in fields and fields["type"] not in VALID_TOOL_TYPES:
        raise ValidationError(
            f"Invalid tool type '{fields['type']}'. "
            f"Must be one of: {', '.join(sorted(VALID_TOOL_TYPES))}"
        )

    for key, value in fields.items():
        if hasattr(tool, key):
            setattr(tool, key, value)

    await db.commit()
    await db.refresh(tool)
    return tool


async def delete_tool(db: AsyncSession, tool_id: str) -> None:
    """Delete a tool by ID. Raises NotFoundError if missing."""
    tool = await get_tool_by_id(db, tool_id)
    if tool is None:
        raise NotFoundError("Tool not found")

    await db.delete(tool)
    await db.commit()
