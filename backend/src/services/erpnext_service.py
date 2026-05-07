# =============================================================================
# PH Agent Hub — ERPNext Instance Service (CRUD)
# =============================================================================

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import NotFoundError
from ..db.orm.erpnext_instances import ERPNextInstance


async def list_erpnext_instances(
    db: AsyncSession, tenant_id: str | None = None
) -> list[ERPNextInstance]:
    """Return all ERPNext instances, optionally filtered by tenant_id."""
    stmt = select(ERPNextInstance)
    if tenant_id is not None:
        stmt = stmt.where(ERPNextInstance.tenant_id == tenant_id)
    stmt = stmt.order_by(ERPNextInstance.created_at)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_erpnext_instance_by_id(
    db: AsyncSession, instance_id: str
) -> ERPNextInstance | None:
    """Look up an ERPNext instance by primary key."""
    result = await db.execute(
        select(ERPNextInstance).where(ERPNextInstance.id == instance_id)
    )
    return result.scalar_one_or_none()


async def create_erpnext_instance(
    db: AsyncSession,
    tenant_id: str,
    base_url: str,
    api_key: str,
    api_secret: str,
    version: str,
) -> ERPNextInstance:
    """Create a new ERPNext instance. api_key and api_secret are
    transparently encrypted by the ORM."""
    instance = ERPNextInstance(
        tenant_id=tenant_id,
        base_url=base_url,
        api_key=api_key,
        api_secret=api_secret,
        version=version,
    )
    db.add(instance)
    await db.commit()
    await db.refresh(instance)
    return instance


async def update_erpnext_instance(
    db: AsyncSession, instance_id: str, **fields
) -> ERPNextInstance:
    """Update an ERPNext instance's fields. Raises NotFoundError if missing."""
    instance = await get_erpnext_instance_by_id(db, instance_id)
    if instance is None:
        raise NotFoundError("ERPNext instance not found")

    for key, value in fields.items():
        if hasattr(instance, key):
            setattr(instance, key, value)

    await db.commit()
    await db.refresh(instance)
    return instance


async def delete_erpnext_instance(db: AsyncSession, instance_id: str) -> None:
    """Delete an ERPNext instance by ID. Raises NotFoundError if missing."""
    instance = await get_erpnext_instance_by_id(db, instance_id)
    if instance is None:
        raise NotFoundError("ERPNext instance not found")

    await db.delete(instance)
    await db.commit()
