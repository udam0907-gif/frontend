"""Legal tables and QA session v2

Revision ID: 002
Revises: 001
Create Date: 2026-04-17 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fix rcms_chunks embedding dimension (001 wrongly set 1536, model uses 384)
    op.execute(
        "ALTER TABLE rcms_chunks ALTER COLUMN embedding TYPE vector(384) USING NULL::vector(384)"
    )

    # Recreate index with correct dimension
    op.execute("DROP INDEX IF EXISTS ix_rcms_chunks_embedding")
    op.execute(
        "CREATE INDEX ix_rcms_chunks_embedding ON rcms_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    # Fix missing columns in rcms_manuals (001 was missing some)
    try:
        op.add_column(
            "rcms_manuals",
            sa.Column("original_filename", sa.String(500), nullable=True),
        )
    except Exception:
        pass
    try:
        op.add_column(
            "rcms_manuals", sa.Column("parse_error", sa.Text, nullable=True)
        )
    except Exception:
        pass
    try:
        op.add_column(
            "rcms_manuals", sa.Column("total_chunks", sa.Integer, nullable=True)
        )
    except Exception:
        pass
    try:
        op.add_column(
            "rcms_manuals", sa.Column("total_pages", sa.Integer, nullable=True)
        )
    except Exception:
        pass
    try:
        op.add_column(
            "rcms_manuals",
            sa.Column(
                "metadata",
                postgresql.JSONB,
                nullable=True,
                server_default="{}",
            ),
        )
    except Exception:
        pass
    try:
        op.add_column(
            "rcms_manuals",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
        )
    except Exception:
        pass
    try:
        op.add_column(
            "rcms_manuals",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
        )
    except Exception:
        pass

    # Fix rcms_qa_sessions missing columns
    try:
        op.add_column(
            "rcms_qa_sessions",
            sa.Column(
                "token_usage",
                postgresql.JSONB,
                nullable=True,
                server_default="{}",
            ),
        )
    except Exception:
        pass
    try:
        op.add_column(
            "rcms_qa_sessions",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
        )
    except Exception:
        pass
    try:
        op.add_column(
            "rcms_qa_sessions",
            sa.Column("question_type", sa.String(50), nullable=True),
        )
    except Exception:
        pass
    try:
        op.add_column(
            "rcms_qa_sessions",
            sa.Column("normalized_query", sa.Text, nullable=True),
        )
    except Exception:
        pass
    try:
        op.add_column(
            "rcms_qa_sessions",
            sa.Column("expanded_queries", postgresql.JSONB, nullable=True),
        )
    except Exception:
        pass
    try:
        op.add_column(
            "rcms_qa_sessions",
            sa.Column("routing_decision", sa.String(50), nullable=True),
        )
    except Exception:
        pass
    try:
        op.add_column(
            "rcms_qa_sessions",
            sa.Column("rule_cards", postgresql.JSONB, nullable=True),
        )
    except Exception:
        pass
    try:
        op.add_column(
            "rcms_qa_sessions",
            sa.Column("answerability_status", sa.String(100), nullable=True),
        )
    except Exception:
        pass

    # Create legal_docs table
    op.create_table(
        "legal_docs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("law_name", sa.String(255), nullable=False),
        sa.Column("law_mst", sa.String(50), nullable=True),
        sa.Column(
            "source_type", sa.String(50), nullable=False, server_default="api"
        ),
        sa.Column("promulgation_date", sa.String(20), nullable=True),
        sa.Column("effective_date", sa.String(20), nullable=True),
        sa.Column("total_articles", sa.Integer, nullable=True),
        sa.Column("total_chunks", sa.Integer, nullable=True),
        sa.Column(
            "sync_status",
            sa.Enum(
                "pending",
                "processing",
                "completed",
                "failed",
                name="parse_status",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("sync_error", sa.Text, nullable=True),
        sa.Column("raw_content", sa.Text, nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Create legal_chunks table (embedding starts as Text, will be converted below)
    op.create_table(
        "legal_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "doc_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("legal_docs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("article_number", sa.String(50), nullable=True),
        sa.Column("article_title", sa.String(500), nullable=True),
        sa.Column("section_title", sa.String(500), nullable=True),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("embedding", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Convert legal_chunks.embedding to vector(384)
    op.execute(
        "ALTER TABLE legal_chunks ALTER COLUMN embedding TYPE vector(384) USING NULL::vector(384)"
    )

    # Create vector index for legal_chunks
    op.execute(
        "CREATE INDEX ix_legal_chunks_embedding ON legal_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50)"
    )

    # trgm index for keyword search on legal_chunks
    op.execute(
        "CREATE INDEX ix_legal_chunks_trgm ON legal_chunks "
        "USING gin (chunk_text gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_legal_chunks_trgm")
    op.execute("DROP INDEX IF EXISTS ix_legal_chunks_embedding")
    op.drop_table("legal_chunks")
    op.drop_table("legal_docs")
