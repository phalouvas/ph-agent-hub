# =============================================================================
# PH Agent Hub — ORM: RAG Documents
# =============================================================================

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey, JSON, func
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from .tenants import Tenant


class RAGDocument(Base):
    __tablename__ = "rag_documents"

    id: Mapped[str] = mapped_column(
        CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("tenants.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    vector_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
