from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import UUID, Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DocumentSetSpec(Base):
    __tablename__ = "document_set_specs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    doc_kind: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    template_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    upload_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    allowed_extensions: Mapped[list] = mapped_column(
        JSONB, nullable=False,
        default=lambda: [".pdf", ".jpg", ".jpeg", ".png", ".xlsx", ".docx"],
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("category", "doc_kind", name="uq_doc_set_specs_cat_kind"),
    )
