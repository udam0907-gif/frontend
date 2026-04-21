from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class GeneratedDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    expense_item_id: uuid.UUID
    template_id: uuid.UUID | None
    output_path: str
    generation_trace: dict[str, Any]
    is_valid: bool
    created_at: datetime
    updated_at: datetime


class ValidationIssue(BaseModel):
    code: str
    message: str
    field: str | None = None
    severity: str = "error"


class ValidationResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    expense_item_id: uuid.UUID
    blocking_errors: list[ValidationIssue]
    warnings: list[ValidationIssue]
    passed_checks: list[str]
    is_valid: bool
    created_at: datetime
    updated_at: datetime


class GenerateDocumentRequest(BaseModel):
    expense_item_id: uuid.UUID
    template_id: uuid.UUID
    field_values: dict[str, Any]
