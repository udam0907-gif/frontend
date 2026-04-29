from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


VendorCategory = Literal["매입처", "매출처"]


class VendorCreate(BaseModel):
    project_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    vendor_category: VendorCategory
    business_number: str = Field(min_length=1, max_length=20)
    contact: str | None = None


class VendorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    name: str
    vendor_category: str
    business_number: str
    contact: str | None
    business_registration_path: str | None
    bank_copy_path: str | None
    quote_template_path: str | None
    transaction_statement_path: str | None
    created_at: datetime
    updated_at: datetime


class VendorUpdate(BaseModel):
    name: str | None = None
    vendor_category: VendorCategory | None = None
    business_number: str | None = None
    contact: str | None = None
