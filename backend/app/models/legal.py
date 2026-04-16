from __future__ import annotations

import uuid

from sqlalchemy import UUID, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin
from app.models.enums import ParseStatus

try:
    from pgvector.sqlalchemy import Vector
    _vector_available = True
except ImportError:
    _vector_available = False

try:
    from sqlalchemy.dialects.postgresql import JSONB
except ImportError:
    JSONB = None


class LegalDocument(Base, TimestampMixin):
    """
    A Korean legal/regulatory document fetched from Korea Law Open API
    or uploaded manually. Stored separately from RCMS manuals.

    Supported sources:
    - 국가연구개발혁신법
    - 국가연구개발혁신법 시행령
    - 국가연구개발사업 연구개발비 사용 기준
    - Other ministry-specific operating rules
    """
    __tablename__ = "legal_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Human-readable name shown in UI
    law_name: Mapped[str] = mapped_column(String(300), nullable=False)
    # Unique MST code from Korea Law Open API (or manual upload identifier)
    law_mst: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    # Source: "api" = fetched from Korea Law API, "upload" = manually uploaded
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="api")
    promulgation_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    effective_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    total_articles: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_chunks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sync_status: Mapped[ParseStatus] = mapped_column(
        Enum(ParseStatus, name="parse_status"), nullable=False, default=ParseStatus.pending
    )
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    chunks: Mapped[list[LegalChunk]] = relationship(
        "LegalChunk", back_populates="document", cascade="all, delete-orphan"
    )


class LegalChunk(Base):
    """
    A single retrieval unit from a legal document.
    Each chunk corresponds roughly to one article (조) or
    a 800-char window of article text for long articles.
    """
    __tablename__ = "legal_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("legal_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Article reference, e.g. "제15조", "제15조제2항", null for preamble
    article_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Article title, e.g. "연구개발비의 사용"
    article_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    if _vector_available:
        embedding: Mapped[list[float] | None] = mapped_column(
            Vector(384), nullable=True
        )
    else:
        from sqlalchemy.dialects.postgresql import JSONB as _JSONB
        embedding: Mapped[list | None] = mapped_column(_JSONB, nullable=True)

    document: Mapped[LegalDocument] = relationship("LegalDocument", back_populates="chunks")
