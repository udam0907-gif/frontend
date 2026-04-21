from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

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
    source_type: str  # "legal" | "rcms"
    # RCMS fields
    manual_id: str | None = None
    display_name: str | None = None
    # Legal fields
    law_name: str | None = None
    article_number: str | None = None
    article_title: str | None = None
    # Common
    page: int | None = None
    section_title: str | None = None
    excerpt: str
    confidence: float
    chunk_id: str | None = None
    is_decisive: bool = False


class QuestionUnderstandingInfo(BaseModel):
    question_type: str
    normalized_query: str
    expanded_queries: list[str]
    routing_decision: str


class RcmsQaRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    manual_ids: list[uuid.UUID] | None = None
    debug: bool = False


class RcmsQaResponse(BaseModel):
    question_type: str
    short_answer: str
    conclusion: str | None = None
    conditions_or_exceptions: str | None = None
    legal_basis: str | None = None
    rcms_steps: str | None = None
    detailed_explanation: str
    further_confirmation_needed: bool = False
    confidence: str = "low"
    evidence: list[EvidenceItem]
    found_in_manual: bool
    answer_status: str
    answer_status_type: str
    question_understanding: QuestionUnderstandingInfo | None = None
    debug: dict[str, Any] | None = None
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
    question_type: str | None
    answerability_status: str | None
    created_at: datetime
    updated_at: datetime
