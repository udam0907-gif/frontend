from __future__ import annotations

import uuid

from sqlalchemy import UUID, Boolean, Enum, Integer, String, Text
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
    # field_map structure: {
    #   "placeholder_name": {
    #     "label": "한국어 레이블",
    #     "type": "text|number|date|helper_text",
    #     "required": true,
    #     "source": "user_input|project_data|llm_generated"
    #   }
    # }
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    generated_documents: Mapped[list] = relationship(
        "GeneratedDocument", back_populates="template"
    )
