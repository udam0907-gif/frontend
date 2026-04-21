from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ParseStatus


class LegalDocRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    law_name: str
    law_mst: str | None
    source_type: str
    promulgation_date: str | None
    effective_date: str | None
    total_articles: int | None
    total_chunks: int | None
    sync_status: ParseStatus
    sync_error: str | None
    created_at: datetime
    updated_at: datetime


class LegalSyncRequest(BaseModel):
    law_name: str = Field(min_length=1, max_length=200)
    law_mst: str | None = None


class LegalSyncResponse(BaseModel):
    message: str
    law_name: str


class LegalSyncDefaultsResponse(BaseModel):
    message: str
    laws: list[str]
