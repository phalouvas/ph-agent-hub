# =============================================================================
# PH Agent Hub — ORM: User Tool Preferences
# =============================================================================

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from .users import User
from .tools import Tool


class UserToolPreference(Base):
    __tablename__ = "user_tool_preferences"

    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.id"), primary_key=True
    )
    tool_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("tools.id"), primary_key=True
    )
    always_on: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
