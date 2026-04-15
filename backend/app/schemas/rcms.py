from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ParseStatus


class RcmsManualRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    original_filename: str
    display_name: str
    file_path: str
    file_size: int | None
    version: str
    parse_status: ParseStatus
    total_pages: int | None
    total_chunks: int | None
    parse_error: str | None
    metadata_: dict[str, Any] = Field(alias="metadata_")
    created_at: datetime
    updated_at: datetime


class RcmsChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    manual_id: uuid.UUID
    page_number: int
    section_title: str | None
    chunk_text: str
    chunk_index: int


class EvidenceItem(BaseModel):
    """Evidence citation linked to an uploaded RCMS manual chunk."""
    manual_id: str
    display_name: str
    page: int | None = None
    section_title: str | None = None
    excerpt: str
    confidence: float
    chunk_id: str | None = None


class RcmsQaRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    manual_ids: list[uuid.UUID] | None = None


class RcmsQaResponse(BaseModel):
    """Immediate answer returned by the /rcms/qa endpoint."""
    short_answer: str
    detailed_explanation: str
    evidence: list[EvidenceItem]
    found_in_manual: bool
    answer_status: Literal["answered_with_evidence", "not_found_in_uploaded_manuals"]
    model_version: str
    prompt_version: str


class RcmsQaSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question: str
    answer: dict[str, Any]
    retrieved_chunks: list[Any]
    model_version: str
    prompt_version: str
    token_usage: dict[str, Any]
    created_at: datetime
    updated_at: datetime
