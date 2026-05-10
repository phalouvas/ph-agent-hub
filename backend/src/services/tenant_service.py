# =============================================================================
# PH Agent Hub — Tenant Service (CRUD)
# =============================================================================

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import ConflictError, NotFoundError
from ..db.orm.tenants import Tenant


async def list_tenants(db: AsyncSession) -> list[Tenant]:
    """Return all tenants."""
    result = await db.execute(select(Tenant).order_by(Tenant.created_at))
    return list(result.scalars().all())


async def get_tenant_by_id(db: AsyncSession, tenant_id: str) -> Tenant | None:
    """Look up a tenant by primary key."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


async def create_tenant(db: AsyncSession, name: str) -> Tenant:
    """Create a new tenant. Raises ConflictError if the name already exists."""
    existing = await db.execute(select(Tenant).where(Tenant.name == name))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("A tenant with this name already exists")

    tenant = Tenant(name=name)
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


async def update_tenant(db: AsyncSession, tenant_id: str, name: str) -> Tenant:
    """Update a tenant's name. Raises NotFoundError or ConflictError."""
    tenant = await get_tenant_by_id(db, tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant not found")

    duplicate = await db.execute(
        select(Tenant).where(Tenant.name == name, Tenant.id != tenant_id)
    )
    if duplicate.scalar_one_or_none() is not None:
        raise ConflictError("A tenant with this name already exists")

    tenant.name = name
    await db.commit()
    await db.refresh(tenant)
    return tenant


async def delete_tenant(db: AsyncSession, tenant_id: str) -> None:
    """Delete a tenant by ID. Raises NotFoundError if missing, ConflictError
    if the tenant still has active resources (users, models, sessions, etc.).
    Audit/usage logs are auto-cleaned up (they are historical records)."""
    tenant = await get_tenant_by_id(db, tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant not found")

    # ------------------------------------------------------------------
    # Auto-cleanup: historical records that shouldn't block deletion
    # ------------------------------------------------------------------
    from ..db.orm.audit_logs import AuditLog
    from ..db.orm.usage_logs import UsageLog

    await db.execute(delete(AuditLog).where(AuditLog.tenant_id == tenant_id))
    await db.execute(delete(UsageLog).where(UsageLog.tenant_id == tenant_id))
    await db.flush()

    # ------------------------------------------------------------------
    # Blocker check: active resources that must be handled manually
    # ------------------------------------------------------------------
    blockers: list[str] = []

    from ..db.orm.users import User
    from ..db.orm.sessions import Session as SessionORM
    from ..db.orm.tools import Tool
    from ..db.orm.templates import Template
    from ..db.orm.skills import Skill
    from ..db.orm.tags import Tag as TagORM
    from ..db.orm.memory import Memory
    from ..db.orm.file_uploads import FileUpload
    from ..db.orm.models import Model as ModelORM
    from ..db.orm.groups import UserGroup
    from ..db.orm.prompts import Prompt
    from ..db.orm.rag import RAGDocument

    checks: list[tuple[str, type]] = [
        ("users", User),
        ("models", ModelORM),
        ("sessions", SessionORM),
        ("tools", Tool),
        ("templates", Template),
        ("skills", Skill),
        ("tags", TagORM),
        ("memories", Memory),
        ("file uploads", FileUpload),
        ("user groups", UserGroup),
        ("prompts", Prompt),
        ("RAG documents", RAGDocument),
    ]

    for label, model in checks:
        result = await db.execute(
            select(func.count()).select_from(model).where(
                getattr(model, "tenant_id") == tenant_id
            )
        )
        count = result.scalar() or 0
        if count > 0:
            blockers.append(f"{count} {label}")

    if blockers:
        raise ConflictError(
            "Cannot delete this tenant — it still has related data: "
            + ", ".join(blockers)
            + ". Remove or reassign all related resources first."
        )

    await db.delete(tenant)
    await db.commit()
