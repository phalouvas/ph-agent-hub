# =============================================================================
# PH Agent Hub — ORM: User Groups & Model Groups
# =============================================================================

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from .tenants import Tenant
from .users import User
from .models import Model
from .tools import Tool


class UserGroup(Base):
    __tablename__ = "user_groups"

    id: Mapped[str] = mapped_column(
        CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("tenants.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserGroupMember(Base):
    __tablename__ = "user_group_members"

    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.id"), primary_key=True
    )
    group_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("user_groups.id"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ModelGroup(Base):
    __tablename__ = "model_groups"

    model_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("models.id"), primary_key=True
    )
    group_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("user_groups.id"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ToolGroup(Base):
    __tablename__ = "tool_groups"

    tool_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("tools.id"), primary_key=True
    )
    group_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("user_groups.id"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
