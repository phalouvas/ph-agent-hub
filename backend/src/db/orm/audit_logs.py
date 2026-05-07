# =============================================================================
# PH Agent Hub — ORM: Audit Logs (Append-Only)
# =============================================================================

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Enum, ForeignKey, JSON, func
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from .tenants import Tenant
from .users import User


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("tenants.id"), nullable=True
    )
    actor_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.id"), nullable=False
    )
    actor_role: Mapped[str] = mapped_column(
        Enum("admin", "manager", "user", name="audit_actor_role_enum"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
