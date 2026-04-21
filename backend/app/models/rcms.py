from __future__ import annotations

import uuid

from sqlalchemy import UUID, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin
from app.models.enums import ParseStatus

try:
    from pgvector.sqlalchemy import Vector
    _vector_available = True
except ImportError:
    _vector_available = False


class RcmsManual(Base, TimestampMixin):
    __tablename__ = "rcms_manuals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0")
    parse_status: Mapped[ParseStatus] = mapped_column(
        Enum(ParseStatus, name="parse_status"), nullable=False, default=ParseStatus.pending
    )
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_chunks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )

    chunks: Mapped[list[RcmsChunk]] = relationship(
        "RcmsChunk", back_populates="manual", cascade="all, delete-orphan"
    )


class RcmsChunk(Base):
    __tablename__ = "rcms_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    manual_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rcms_manuals.id", ondelete="CASCADE"),
        nullable=False,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    section_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    if _vector_available:
        embedding: Mapped[list[float] | None] = mapped_column(
            Vector(384), nullable=True
        )
    else:
        embedding: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    manual: Mapped[RcmsManual] = relationship("RcmsManual", back_populates="chunks")


class RcmsQaSession(Base, TimestampMixin):
    __tablename__ = "rcms_qa_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # answer structure:
    # {
    #   "short_answer": "...",
    #   "detailed_explanation": "...",
    #   "evidence": [
    #     {
    #       "chunk_id": "uuid",
    #       "page": 5,
    #       "section": "3.2 집행 절차",
    #       "excerpt": "...",
    #       "confidence": 0.92
    #     }
    #   ],
    #   "found_in_manual": true
    # }
    retrieved_chunks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    token_usage: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    question_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    normalized_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    expanded_queries: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    routing_decision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rule_cards: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    answerability_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
