from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CategoryType, DocumentType


class FieldMapEntry(BaseModel):
    label: str
    type: str = "text"
    required: bool = True
    source: str = "user_input"
    description: str | None = None


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category_type: CategoryType
    document_type: DocumentType
    version: str = "1.0.0"
    description: str | None = None


class TemplateUpdate(BaseModel):
    name: str | None = None
    version: str | None = None
    description: str | None = None
    is_active: bool | None = None
    field_map: dict[str, Any] | None = None
    layout_map: dict[str, Any] | None = None


class TemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category_type: CategoryType
    document_type: DocumentType
    filename: str
    file_path: str
    version: str
    field_map: dict[str, Any]
    layout_map: dict[str, Any] | None = None
    is_active: bool
    description: str | None
    project_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
