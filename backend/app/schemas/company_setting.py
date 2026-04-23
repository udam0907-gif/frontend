from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CompanySettingFileStatus(BaseModel):
    path: str | None = None
    exists: bool = False
    file_name: str | None = None
    updated_at: datetime | None = None


class CompanySettingUpsert(BaseModel):
    company_id: str = "default"
    company_name: str | None = None
    company_registration_number: str | None = None
    representative_name: str | None = None
    address: str | None = None
    business_type: str | None = None
    business_item: str | None = None
    phone: str | None = None
    fax: str | None = None
    email: str | None = None
    default_manager_name: str | None = None
    seal_image_path: str | None = None
    company_business_registration_path: str | None = None
    company_bank_copy_path: str | None = None
    company_quote_template_path: str | None = None
    company_transaction_statement_template_path: str | None = None


class CompanySettingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None
    company_id: str = "default"
    company_name: str | None = None
    company_registration_number: str | None = None
    representative_name: str | None = None
    address: str | None = None
    business_type: str | None = None
    business_item: str | None = None
    phone: str | None = None
    fax: str | None = None
    email: str | None = None
    default_manager_name: str | None = None
    seal_image_path: str | None = None
    company_business_registration_path: str | None = None
    company_bank_copy_path: str | None = None
    company_quote_template_path: str | None = None
    company_transaction_statement_template_path: str | None = None
    file_statuses: dict[str, CompanySettingFileStatus] = {}
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CompanySettingExtractedFields(BaseModel):
    company_name: str | None = None
    company_registration_number: str | None = None
    representative_name: str | None = None
    address: str | None = None
    business_type: str | None = None
    business_item: str | None = None
    phone: str | None = None
    fax: str | None = None
    email: str | None = None


class CompanySettingExtractResponse(BaseModel):
    company_id: str = "default"
    extracted: CompanySettingExtractedFields
    source_by_field: dict[str, str]
    used_files: list[str]
