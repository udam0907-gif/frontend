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
    """
    Evidence citation from either a legal document or an RCMS manual chunk.
    Use source_type to distinguish the two in the UI.
    """
    # "legal" = from Korea Law API / legal documents
    # "rcms"  = from uploaded RCMS manuals
    source_type: Literal["legal", "rcms"] = "rcms"

    # RCMS manual fields (populated when source_type == "rcms")
    manual_id: str | None = None
    display_name: str = ""

    # Legal document fields (populated when source_type == "legal")
    law_name: str | None = None        # e.g. "국가연구개발혁신법"
    article_number: str | None = None  # e.g. "제15조"
    article_title: str | None = None   # e.g. "연구개발비의 사용"

    # Common fields
    page: int | None = None
    section_title: str | None = None
    excerpt: str
    confidence: float
    chunk_id: str | None = None


class RcmsQaRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    manual_ids: list[uuid.UUID] | None = None


class DebugCandidate(BaseModel):
    """One of the top-5 retrieval candidates shown for debugging."""
    rank: int
    source_type: str = "rcms"  # "legal" | "rcms"
    display_name: str
    page: int | None = None
    section_title: str | None = None
    similarity: float
    match_type: str  # "vector" | "keyword" | "hybrid"
    excerpt: str


class RcmsQaResponse(BaseModel):
    """
    Dual-source answer returned by the /rcms/qa endpoint.

    question_type:
      - rcms_procedure  → answered from RCMS manuals only
      - legal_policy    → answered from legal/regulatory sources
      - mixed           → legal conclusion first, then RCMS procedure steps
    """
    question_type: Literal["rcms_procedure", "legal_policy", "mixed"] = "rcms_procedure"

    # Always present
    short_answer: str
    detailed_explanation: str
    found_in_manual: bool
    answer_status: Literal["answered_with_evidence", "not_found_in_uploaded_manuals"]
    model_version: str
    prompt_version: str

    # Legal/mixed: law conclusion + cited articles
    conclusion: str | None = None
    legal_basis: str | None = None

    # RCMS/mixed: system handling procedure
    rcms_steps: str | None = None

    # Evidence split by source type
    evidence: list[EvidenceItem] = []

    debug_candidates: list[DebugCandidate] = []


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


# ─── Legal document schemas ───────────────────────────────────────────────────

class LegalDocRead(BaseModel):
    """Summary of an ingested legal document shown in the sidebar / law list."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    law_name: str
    law_mst: str
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
    """Request body to trigger sync for a single law by name."""
    law_name: str = Field(min_length=1, max_length=200,
                          description="법령명 (예: 국가연구개발혁신법)")
    # If known, caller can supply the MST code to skip the search step
    law_mst: str | None = None
    # "law" for 법령/시행령, "admrul" for 행정규칙(고시)
    api_target: str = "law"
