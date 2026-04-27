from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class VendorPoolRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vendor_business_number: str
    vendor_name: str
    file_format: str
    layout_map: dict[str, Any]
    render_profile: dict[str, Any]
    field_map: dict[str, Any]
    verified: bool
    verified_count: int
    created_at: datetime
    updated_at: datetime


class CompanyVendorTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    pool_id: uuid.UUID
    vendor_alias: str | None
    custom_override: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime
