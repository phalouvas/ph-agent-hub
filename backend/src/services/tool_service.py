# =============================================================================
# PH Agent Hub — Tool Service (CRUD)
# =============================================================================

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import NotFoundError, ValidationError
from ..db.orm.groups import ToolGroup, UserGroupMember
from ..db.orm.tools import Tool

VALID_TOOL_TYPES = {
    "erpnext", "membrane", "custom", "datetime", "web_search",
    "fetch_url", "weather", "calculator", "wikipedia", "rss_feed",
    "currency_exchange", "market_overview", "etf_data", "stock_data",
    "portfolio", "sec_filings",
    "code_interpreter", "sql_query", "document_generation", "browser",
}

TOOL_TYPE_TO_CATEGORY = {
    "currency_exchange": "financial",
    "market_overview": "financial",
    "etf_data": "financial",
    "stock_data": "financial",
    "portfolio": "financial",
    "sec_filings": "financial",
    "web_search": "web",
    "fetch_url": "web",
    "rss_feed": "web",
    "wikipedia": "web",
    "erpnext": "enterprise",
    "membrane": "enterprise",
    "calculator": "utility",
    "datetime": "utility",
    "weather": "utility",
    "custom": "custom",
    "code_interpreter": "utility",
    "sql_query": "enterprise",
    "document_generation": "utility",
    "browser": "web",
    "file_list": "system",
    "memory": "system",
}


def derive_tool_category(tool_type: str) -> str:
    """Map tool type to category. Unknown types fall back to general."""
    return TOOL_TYPE_TO_CATEGORY.get(tool_type, "general")


async def list_tools(
    db: AsyncSession,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> list[Tool]:
    """Return all tools, optionally filtered by tenant_id and user access.

    When user_id is provided, only returns tools where:
    - is_public=True, OR
    - the tool is assigned to a group the user belongs to
    """
    stmt = select(Tool)
    if tenant_id is not None:
        stmt = stmt.where(Tool.tenant_id == tenant_id)

    if user_id is not None:
        # Subquery: tool IDs assigned to groups the user belongs to
        user_group_subq = (
            select(ToolGroup.tool_id)
            .join(UserGroupMember, UserGroupMember.group_id == ToolGroup.group_id)
            .where(UserGroupMember.user_id == user_id)
        )
        stmt = stmt.where(
            or_(
                Tool.is_public == True,  # noqa: E712
                Tool.id.in_(user_group_subq),
            )
        )

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
    code: str | None = None,
    enabled: bool = True,
    is_public: bool = False,
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
        code=code,
        enabled=enabled,
        is_public=is_public,
        category=derive_tool_category(type),
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
    # Category is system-derived from type and not user-editable.
    fields.pop("category", None)

    if "type" in fields:
        fields["category"] = derive_tool_category(fields["type"])

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
