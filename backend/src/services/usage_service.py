# =============================================================================
# PH Agent Hub — Usage Service
# =============================================================================
# DB helpers for writing and querying usage log rows.
# =============================================================================

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.orm.usage_logs import UsageLog


async def write_usage_log(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    model_id: str,
    tokens_in: int,
    tokens_out: int,
) -> UsageLog:
    """Create and persist a usage log row."""
    log = UsageLog(
        tenant_id=tenant_id,
        user_id=user_id,
        model_id=model_id,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )
    db.add(log)
    await db.commit()
    return log


async def list_usage_logs(
    db: AsyncSession,
    *,
    tenant_id: str | None = None,
    user_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[UsageLog]:
    """Query usage logs, optionally filtered by tenant and/or user."""
    stmt = select(UsageLog).order_by(UsageLog.created_at.desc())

    if tenant_id is not None:
        stmt = stmt.where(UsageLog.tenant_id == tenant_id)
    if user_id is not None:
        stmt = stmt.where(UsageLog.user_id == user_id)

    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())
