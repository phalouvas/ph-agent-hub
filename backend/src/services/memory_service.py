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
