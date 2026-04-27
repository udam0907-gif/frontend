from __future__ import annotations

import uuid

from sqlalchemy import UUID, Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin
from app.models.enums import CategoryType, DocumentType


class Template(Base, TimestampMixin):
    __tablename__ = "templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category_type: Mapped[CategoryType] = mapped_column(
        Enum(CategoryType, name="category_type", create_type=False), nullable=False
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    field_map: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    file_format: Mapped[str] = mapped_column(String(10), nullable=False, server_default="docx")
    # field_map: 기존 flat 구조 — 렌더링 엔진이 현재 사용
    #   {"field_key": {"label": "...", "type": "...", "cell": "B4", ...}}
    layout_map: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)
    # layout_map: XLSX 구조 명세 — layout_map 렌더러 전용
    #   {"document_type": "...", "scalar_fields": {...}, "checkbox_fields": {...}, "table_fields": {...}}
    render_profile: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)
    # render_profile: DOCX 렌더 전략 프로파일 — 견적서 등 회사별 양식 대응
    #   {"doc_type": "quote", "render_strategy": "marker_table|paragraph_fill|standard_table|docxtpl", ...}
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    generated_documents: Mapped[list] = relationship(
        "GeneratedDocument", back_populates="template"
    )
