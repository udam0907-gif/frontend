from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CategoryType, DocumentType, ExpenseStatus, UploadStatus


class ExpenseItemCreate(BaseModel):
    project_id: uuid.UUID
    category_type: CategoryType
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    amount: Decimal = Field(gt=0)
    expense_date: str | None = None
    vendor_name: str | None = None
    vendor_registration_number: str | None = None
    metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata")

    model_config = ConfigDict(populate_by_name=True)


class ExpenseItemUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    amount: Decimal | None = Field(None, gt=0)
    expense_date: str | None = None
    vendor_name: str | None = None
    vendor_registration_number: str | None = None
    status: ExpenseStatus | None = None
    metadata_: dict[str, Any] | None = Field(None, alias="metadata")

    model_config = ConfigDict(populate_by_name=True)


class ExpenseDocumentCreate(BaseModel):
    expense_item_id: uuid.UUID
    document_type: DocumentType


class ExpenseDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    expense_item_id: uuid.UUID
    document_type: DocumentType
    filename: str
    file_path: str
    file_size: int | None
    mime_type: str | None
    upload_status: UploadStatus
    extracted_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ExpenseItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    project_id: uuid.UUID
    category_type: CategoryType
    title: str
    description: str | None
    amount: Decimal
    status: ExpenseStatus
    expense_date: str | None
    vendor_name: str | None
    vendor_registration_number: str | None
    input_data: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")
    created_at: datetime
    updated_at: datetime
    documents: list[ExpenseDocumentRead] = []
