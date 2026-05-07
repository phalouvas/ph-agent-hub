# =============================================================================
# PH Agent Hub — Tenant Service (CRUD)
# =============================================================================

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
    if the tenant still has users assigned to it."""
    tenant = await get_tenant_by_id(db, tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant not found")

    db.add(tenant)
    await db.delete(tenant)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError(
            "Cannot delete tenant that still has users. Remove all users first."
        )
