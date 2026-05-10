# =============================================================================
# PH Agent Hub — Template Service (CRUD + join table management)
# =============================================================================

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import NotFoundError
from ..db.orm.templates import Template, TemplateAllowedTool
from ..db.orm.users import User


async def list_templates(
    db: AsyncSession, tenant_id: str, current_user: User
) -> list[Template]:
    """Return templates visible to the current user within their tenant.

    Visibility rules:
    - scope=tenant: visible to all users in the tenant
    - scope=user: visible only to the assigned user
    - scope=role: visible to admin/manager roles (pending clarification)
    """
    stmt = select(Template).where(Template.tenant_id == tenant_id)

    if current_user.role in ("admin", "manager"):
        # Admin/manager sees all templates in their tenant
        pass
    else:
        # Regular users see tenant-scoped + their own user-scoped templates
        stmt = stmt.where(
            (Template.scope == "tenant")
            | (
                (Template.scope == "user")
                & (Template.assigned_user_id == current_user.id)
            )
        )

    stmt = stmt.order_by(Template.created_at)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_template_by_id(db: AsyncSession, template_id: str) -> Template | None:
    """Look up a template by primary key."""
    result = await db.execute(select(Template).where(Template.id == template_id))
    return result.scalar_one_or_none()


async def list_template_tools(
    db: AsyncSession, template_id: str
) -> list[TemplateAllowedTool]:
    """Return all allowed tool associations for a template."""
    stmt = select(TemplateAllowedTool).where(
        TemplateAllowedTool.template_id == template_id
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _get_template_tool_ids(db: AsyncSession, template_id: str) -> list[str]:
    """Return just the tool_id list for a template."""
    tools = await list_template_tools(db, template_id)
    return [t.tool_id for t in tools]


async def create_template(
    db: AsyncSession,
    tenant_id: str,
    title: str,
    system_prompt: str,
    scope: str,
    description: str | None = None,
    default_model_id: str | None = None,
    assigned_user_id: str | None = None,
    tool_ids: list[str] | None = None,
) -> Template:
    """Create a new template with optional tool associations."""
    template = Template(
        tenant_id=tenant_id,
        title=title,
        description=description,
        system_prompt=system_prompt,
        scope=scope,
        default_model_id=default_model_id,
        assigned_user_id=assigned_user_id,
    )
    db.add(template)
    await db.flush()  # Get the template ID before adding join rows

    # Insert join table rows
    if tool_ids:
        for tid in tool_ids:
            db.add(TemplateAllowedTool(template_id=template.id, tool_id=tid))

    await db.commit()
    await db.refresh(template)
    return template


async def update_template(
    db: AsyncSession,
    template_id: str,
    tool_ids: list[str] | None = None,
    **fields,
) -> Template:
    """Update a template's fields. Replace tool associations if provided.

    Raises NotFoundError if the template does not exist.
    """
    template = await get_template_by_id(db, template_id)
    if template is None:
        raise NotFoundError("Template not found")

    # Update scalar fields
    for key, value in fields.items():
        if hasattr(template, key):
            setattr(template, key, value)

    # Replace join table rows if tool_ids is provided
    if tool_ids is not None:
        await db.execute(
            delete(TemplateAllowedTool).where(
                TemplateAllowedTool.template_id == template_id
            )
        )
        for tid in tool_ids:
            db.add(TemplateAllowedTool(template_id=template_id, tool_id=tid))

    await db.commit()
    await db.refresh(template)
    return template


async def delete_template(db: AsyncSession, template_id: str) -> None:
    """Delete a template by ID. Raises NotFoundError if missing."""
    template = await get_template_by_id(db, template_id)
    if template is None:
        raise NotFoundError("Template not found")

    # Clear FK references in sessions that point to this template
    from ..db.orm.sessions import Session as SessionORM
    from sqlalchemy import update as sa_update

    await db.execute(
        sa_update(SessionORM)
        .where(SessionORM.selected_template_id == template_id)
        .values(selected_template_id=None)
    )

    # Clear FK references in skills that point to this template
    from ..db.orm.skills import Skill as SkillORM

    await db.execute(
        sa_update(SkillORM)
        .where(SkillORM.template_id == template_id)
        .values(template_id=None)
    )

    # Delete join table rows (template_allowed_tools)
    await db.execute(
        delete(TemplateAllowedTool).where(
            TemplateAllowedTool.template_id == template_id
        )
    )

    await db.delete(template)
    await db.commit()
