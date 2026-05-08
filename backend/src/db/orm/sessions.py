# =============================================================================
# PH Agent Hub — ORM: Sessions & Session Active Tools
# =============================================================================

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from .tenants import Tenant
from .users import User
from .templates import Template
from .prompts import Prompt
from .skills import Skill
from .tools import Tool


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    is_temporary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    selected_template_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("templates.id"), nullable=True
    )
    selected_prompt_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("prompts.id"), nullable=True
    )
    selected_skill_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("skills.id"), nullable=True
    )
    selected_model_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("models.id"), nullable=True
    )
    thinking_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SessionActiveTool(Base):
    __tablename__ = "session_active_tools"

    session_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("sessions.id"), primary_key=True
    )
    tool_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("tools.id"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
