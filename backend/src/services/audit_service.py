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
        tenant_name=getattr(actor, "tenant_name", None),  # denormalized snapshot
        actor_id=actor.id,
        actor_role=actor.role,
        actor_email=actor.email,
        actor_full_name=actor.display_name,
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
    search: str | None = None,
    action: str | None = None,
    actor_id: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[AuditLog], int]:
    """Query audit logs with optional filtering, sorting, pagination."""
    stmt = select(AuditLog)

    if tenant_id is not None:
        stmt = stmt.where(AuditLog.tenant_id == tenant_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if actor_id is not None:
        stmt = stmt.where(AuditLog.actor_id == actor_id)

    from ..core.pagination import apply_search, apply_sorting, paginate
    stmt = apply_search(
        stmt, search,
        [AuditLog.action, AuditLog.actor_email, AuditLog.actor_full_name,
         AuditLog.target_type, AuditLog.ip_address],
    )
    stmt = apply_sorting(
        stmt, sort_by, sort_dir,
        column_map={
            "created_at": AuditLog.created_at,
            "action": AuditLog.action,
            "actor_email": AuditLog.actor_email,
        },
        default_sort=AuditLog.created_at.desc(),
    )

    return await paginate(db, stmt, page=page, page_size=page_size)
