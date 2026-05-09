# =============================================================================
# PH Agent Hub — Memory Service
# =============================================================================
# CRUD for the ``memory`` table.  Called by ``api/memory.py``.
# =============================================================================

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import ForbiddenError, NotFoundError
from ..db.orm.memory import Memory


async def list_memory(
    db: AsyncSession,
    user_id: str,
    tenant_id: str,
    session_id: str | None = None,
) -> list[Memory]:
    """List memory entries for a user, optionally scoped to a session."""
    stmt = select(Memory).where(
        Memory.user_id == user_id,
        Memory.tenant_id == tenant_id,
    )
    if session_id is not None:
        stmt = stmt.where(Memory.session_id == session_id)
    stmt = stmt.order_by(Memory.created_at.desc())

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_memory(
    db: AsyncSession,
    tenant_id: str,
    user_id: str,
    key: str,
    value: str,
    session_id: str | None = None,
    source: str = "manual",
) -> Memory:
    """Create a new memory entry."""
    memory = Memory(
        tenant_id=tenant_id,
        user_id=user_id,
        key=key,
        value=value,
        session_id=session_id,
        source=source,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return memory


async def delete_memory(
    db: AsyncSession,
    memory_id: str,
    user_id: str,
    tenant_id: str,
) -> None:
    """Delete a memory entry.  Validates ownership before deleting."""
    result = await db.execute(
        select(Memory).where(Memory.id == memory_id)
    )
    memory = result.scalar_one_or_none()

    if memory is None:
        raise NotFoundError("Memory entry not found")
    if memory.user_id != user_id or memory.tenant_id != tenant_id:
        raise ForbiddenError("You do not own this memory entry")

    await db.execute(delete(Memory).where(Memory.id == memory_id))
    await db.commit()


async def update_memory(
    db: AsyncSession,
    memory_id: str,
    user_id: str,
    tenant_id: str,
    key: str | None = None,
    value: str | None = None,
) -> Memory:
    """Update a memory entry's key and/or value. Validates ownership."""
    result = await db.execute(
        select(Memory).where(Memory.id == memory_id)
    )
    memory = result.scalar_one_or_none()

    if memory is None:
        raise NotFoundError("Memory entry not found")
    if memory.user_id != user_id or memory.tenant_id != tenant_id:
        raise ForbiddenError("You do not own this memory entry")

    if key is not None:
        memory.key = key
    if value is not None:
        memory.value = value

    await db.commit()
    await db.refresh(memory)
    return memory


async def list_all_memories(
    db: AsyncSession,
    tenant_id: str | None = None,
) -> list[Memory]:
    """List all memory entries, optionally scoped to a tenant.  Admin use only."""
    stmt = select(Memory)
    if tenant_id is not None:
        stmt = stmt.where(Memory.tenant_id == tenant_id)
    stmt = stmt.order_by(Memory.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def admin_delete_memory(
    db: AsyncSession,
    memory_id: str,
) -> None:
    """Delete a memory entry by ID.  Admin use only — no ownership check."""
    result = await db.execute(select(Memory).where(Memory.id == memory_id))
    memory = result.scalar_one_or_none()
    if memory is None:
        raise NotFoundError("Memory entry not found")
    await db.execute(delete(Memory).where(Memory.id == memory_id))
    await db.commit()


async def upsert_memory(
    db: AsyncSession,
    user_id: str,
    tenant_id: str,
    key: str,
    value: str,
    session_id: str | None = None,
    source: str = "automatic",
) -> Memory:
    """Insert or update a memory entry by (user_id, tenant_id, key, session_id).

    If an entry with the same user/tenant/key/session_id combo exists,
    its value is updated.  Otherwise a new entry is created.

    Returns the Memory ORM object.
    """
    result = await db.execute(
        select(Memory).where(
            Memory.user_id == user_id,
            Memory.tenant_id == tenant_id,
            Memory.key == key,
            Memory.session_id.is_(None)
            if session_id is None
            else Memory.session_id == session_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.value = value
        await db.commit()
        await db.refresh(existing)
        return existing

    memory = Memory(
        tenant_id=tenant_id,
        user_id=user_id,
        key=key,
        value=value,
        session_id=session_id,
        source=source,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return memory


async def delete_memory_by_key(
    db: AsyncSession,
    user_id: str,
    tenant_id: str,
    key: str,
) -> bool:
    """Delete a memory entry by key (global entries only — session_id IS NULL).

    Returns True if an entry was deleted, False if none was found.
    """
    result = await db.execute(
        select(Memory).where(
            Memory.user_id == user_id,
            Memory.tenant_id == tenant_id,
            Memory.session_id.is_(None),
            Memory.key == key,
        )
    )
    memory = result.scalar_one_or_none()

    if memory is None:
        return False

    await db.execute(delete(Memory).where(Memory.id == memory.id))
    await db.commit()
    return True
