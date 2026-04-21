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


class LegalDoc(Base, TimestampMixin):
    __tablename__ = "legal_docs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    law_name: Mapped[str] = mapped_column(String(255), nullable=False)
    law_mst: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="api")
    promulgation_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    effective_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    total_articles: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_chunks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sync_status: Mapped[ParseStatus] = mapped_column(
        Enum(ParseStatus, name="parse_status"), nullable=False, default=ParseStatus.pending
    )
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)

    chunks: Mapped[list[LegalChunk]] = relationship(
        "LegalChunk", back_populates="doc", cascade="all, delete-orphan"
    )


class LegalChunk(Base):
    __tablename__ = "legal_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("legal_docs.id", ondelete="CASCADE"), nullable=False
    )
    article_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    article_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    section_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    if _vector_available:
        embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    else:
        embedding: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    doc: Mapped[LegalDoc] = relationship("LegalDoc", back_populates="chunks")
