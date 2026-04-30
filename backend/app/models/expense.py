from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import UUID, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin
from app.models.enums import CategoryType, DocumentType, ExpenseStatus, UploadStatus


class ExpenseItem(Base, TimestampMixin):
    __tablename__ = "expense_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_type: Mapped[CategoryType] = mapped_column(
        Enum(CategoryType, name="category_type", create_type=False), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2), nullable=False
    )
    status: Mapped[ExpenseStatus] = mapped_column(
        Enum(ExpenseStatus, name="expense_status"), nullable=False, default=ExpenseStatus.draft
    )
    expense_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    vendor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vendor_registration_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    category_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    project: Mapped[object] = relationship("Project", back_populates="expense_items")
    documents: Mapped[list[ExpenseDocument]] = relationship(
        "ExpenseDocument", back_populates="expense_item", cascade="all, delete-orphan"
    )
    generated_documents: Mapped[list] = relationship(
        "GeneratedDocument", back_populates="expense_item", cascade="all, delete-orphan"
    )
    validation_results: Mapped[list] = relationship(
        "ValidationResult", back_populates="expense_item", cascade="all, delete-orphan"
    )


class ExpenseDocument(Base, TimestampMixin):
    __tablename__ = "expense_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    expense_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expense_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type", create_type=False), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int | None] = mapped_column(nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    upload_status: Mapped[UploadStatus] = mapped_column(
        Enum(UploadStatus, name="upload_status"), nullable=False, default=UploadStatus.pending
    )
    extracted_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    expense_item: Mapped[ExpenseItem] = relationship(
        "ExpenseItem", back_populates="documents"
    )
