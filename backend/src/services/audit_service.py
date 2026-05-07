# =============================================================================
# PH Agent Hub — Audit Service
# =============================================================================
# DB helpers for writing and querying audit log rows.
# =============================================================================

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.orm.audit_logs import AuditLog
from ..db.orm.users import User

logger = logging.getLogger(__name__)

# Sentinel to distinguish "not provided" from explicitly passing None
_SENTINEL = object()


async def write_audit_log(
    db: AsyncSession,
    *,
    actor: User,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    payload: dict | None = None,
    ip_address: str | None = None,
    tenant_id: object = _SENTINEL,
) -> AuditLog:
    """Create and persist an audit log row.

    Args:
        db: Active async DB session.
        actor: The User ORM object performing the action.
        action: A dot-separated action key (e.g. ``"user.created"``).
        target_type: The kind of entity acted upon (e.g. ``"user"``).
        target_id: The primary key of the target entity.
        payload: Optional JSON-serialisable extra context.
            **Never include API keys, passwords, or EncryptedString values.**
        ip_address: The IP address of the request origin.
        tenant_id: The tenant this action belongs to.
            Defaults to ``actor.tenant_id``.  Pass ``None`` explicitly
            for platform-level actions (e.g. tenant creation by admin).

    Returns:
        The newly created AuditLog row.
    """
    if tenant_id is _SENTINEL:
        tenant_id = actor.tenant_id
    elif tenant_id is not None:
        tenant_id = str(tenant_id)

    log = AuditLog(
        tenant_id=tenant_id,  # type: ignore[arg-type]
        actor_id=actor.id,
        actor_role=actor.role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        payload=payload,
        ip_address=ip_address,
    )
    db.add(log)
    await db.commit()
    return log


async def list_audit_logs(
    db: AsyncSession,
    *,
    tenant_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    """Query audit logs, optionally filtered by tenant."""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())

    if tenant_id is not None:
        stmt = stmt.where(AuditLog.tenant_id == tenant_id)

    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())
