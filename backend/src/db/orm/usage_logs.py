# =============================================================================
# PH Agent Hub — ORM: Usage Logs (Append-Only, Denormalized)
# =============================================================================
#
# This table stores denormalized snapshots of each model call.  Foreign keys
# have been removed so that usage data survives tenant/user/model deletion.
# =============================================================================

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Numeric, DateTime, func
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[str] = mapped_column(
        CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # Denormalized entity references (survive deletion)
    tenant_id: Mapped[str] = mapped_column(
        CHAR(36), nullable=False
    )
    tenant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_id: Mapped[str] = mapped_column(
        CHAR(36), nullable=False
    )
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_id: Mapped[str] = mapped_column(
        CHAR(36), nullable=False
    )
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Token counts
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False)
    cache_hit_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Computed cost (currency-neutral; formatted per app setting)
    cost: Mapped[float | None] = mapped_column(Numeric(precision=12, scale=6), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
