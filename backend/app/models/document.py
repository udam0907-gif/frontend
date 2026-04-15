from __future__ import annotations

import uuid

from sqlalchemy import UUID, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin


class GeneratedDocument(Base, TimestampMixin):
    __tablename__ = "generated_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    expense_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expense_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    output_path: Mapped[str] = mapped_column(Text, nullable=False)
    generation_trace: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # generation_trace structure:
    # {
    #   "template_version": "1.0.0",
    #   "model_version": "claude-sonnet-4-6",
    #   "prompt_version": "1.0.0",
    #   "fields_filled": {...},
    #   "llm_fields": [...],
    #   "token_usage": {...},
    #   "validation_passed": true
    # }
    is_valid: Mapped[bool] = mapped_column(nullable=False, default=False)

    expense_item: Mapped[object] = relationship(
        "ExpenseItem", back_populates="generated_documents"
    )
    template: Mapped[object] = relationship(
        "Template", back_populates="generated_documents"
    )


class ValidationResult(Base, TimestampMixin):
    __tablename__ = "validation_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    expense_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expense_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    blocking_errors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    passed_checks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_valid: Mapped[bool] = mapped_column(nullable=False, default=False)

    expense_item: Mapped[object] = relationship(
        "ExpenseItem", back_populates="validation_results"
    )
