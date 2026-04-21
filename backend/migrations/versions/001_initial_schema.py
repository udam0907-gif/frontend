"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-15 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Enums
    project_status = postgresql.ENUM(
        "active", "closed", "suspended", name="project_status", create_type=False
    )
    project_status.create(op.get_bind(), checkfirst=True)

    category_type = postgresql.ENUM(
        "outsourcing", "labor", "test_report", "materials", "meeting", "other",
        name="category_type", create_type=False
    )
    category_type.create(op.get_bind(), checkfirst=True)

    expense_status = postgresql.ENUM(
        "draft", "pending_validation", "validated", "rejected", "exported",
        name="expense_status", create_type=False
    )
    expense_status.create(op.get_bind(), checkfirst=True)

    upload_status = postgresql.ENUM(
        "pending", "uploaded", "failed", name="upload_status", create_type=False
    )
    upload_status.create(op.get_bind(), checkfirst=True)

    parse_status = postgresql.ENUM(
        "pending", "processing", "completed", "failed",
        name="parse_status", create_type=False
    )
    parse_status.create(op.get_bind(), checkfirst=True)

    # projects
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(100), unique=True, nullable=False),
        sa.Column("institution", sa.String(255), nullable=False),
        sa.Column("principal_investigator", sa.String(100), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("total_budget", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.Enum("active", "closed", "suspended", name="project_status"), nullable=False, server_default="active"),
        sa.Column("agreement_file_path", sa.Text, nullable=True),
        sa.Column("plan_file_path", sa.Text, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint("period_end > period_start", name="ck_project_period"),
        sa.CheckConstraint("total_budget > 0", name="ck_project_budget_positive"),
    )

    # budget_categories
    op.create_table(
        "budget_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_type", sa.Enum("outsourcing", "labor", "test_report", "materials", "meeting", "other", name="category_type"), nullable=False),
        sa.Column("allocated_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("spent_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "category_type", name="uq_budget_category"),
        sa.CheckConstraint("allocated_amount >= 0", name="ck_budget_allocated_non_negative"),
        sa.CheckConstraint("spent_amount >= 0", name="ck_budget_spent_non_negative"),
    )

    # templates
    op.create_table(
        "templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("category_type", sa.Enum("outsourcing", "labor", "test_report", "materials", "meeting", "other", name="category_type"), nullable=False),
        sa.Column("document_type", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("field_map", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("uploaded_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("category_type", "document_type", "version", name="uq_template_version"),
    )

    # expense_items
    op.create_table(
        "expense_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_type", sa.Enum("outsourcing", "labor", "test_report", "materials", "meeting", "other", name="category_type"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("vendor_name", sa.String(255), nullable=True),
        sa.Column("expense_date", sa.Date, nullable=True),
        sa.Column("status", sa.Enum("draft", "pending_validation", "validated", "rejected", "exported", name="expense_status"), nullable=False, server_default="draft"),
        sa.Column("input_data", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("amount > 0", name="ck_expense_amount_positive"),
    )

    # expense_documents
    op.create_table(
        "expense_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("expense_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("expense_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_type", sa.String(100), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("file_size", sa.Integer, nullable=True),
        sa.Column("upload_status", sa.Enum("pending", "uploaded", "failed", name="upload_status"), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # generated_documents
    op.create_table(
        "generated_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("expense_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("expense_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("templates.id"), nullable=False),
        sa.Column("output_filename", sa.String(255), nullable=False),
        sa.Column("output_path", sa.Text, nullable=False),
        sa.Column("generation_trace", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # validation_results
    op.create_table(
        "validation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("expense_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("expense_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("blocking_errors", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("warnings", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("passed_checks", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("is_valid", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("validated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # rcms_manuals
    op.create_table(
        "rcms_manuals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(50), nullable=True),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("file_size", sa.Integer, nullable=True),
        sa.Column("parse_status", sa.Enum("pending", "processing", "completed", "failed", name="parse_status"), nullable=False, server_default="pending"),
        sa.Column("chunk_count", sa.Integer, nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # rcms_chunks
    op.create_table(
        "rcms_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("manual_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rcms_manuals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("section_title", sa.String(500), nullable=True),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("embedding", sa.Text, nullable=True),  # stored as JSON string; replace with vector type via raw SQL
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Convert embedding column to pgvector type
    op.execute("ALTER TABLE rcms_chunks ALTER COLUMN embedding TYPE vector(1536) USING NULL::vector(1536)")

    # Create vector index
    op.execute("CREATE INDEX ix_rcms_chunks_embedding ON rcms_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")

    # rcms_qa_sessions
    op.create_table(
        "rcms_qa_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", postgresql.JSONB, nullable=True),
        sa.Column("retrieved_chunks", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("model_version", sa.String(100), nullable=True),
        sa.Column("prompt_version", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("actor", sa.String(255), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("rcms_qa_sessions")
    op.drop_table("rcms_chunks")
    op.drop_table("rcms_manuals")
    op.drop_table("validation_results")
    op.drop_table("generated_documents")
    op.drop_table("expense_documents")
    op.drop_table("expense_items")
    op.drop_table("templates")
    op.drop_table("budget_categories")
    op.drop_table("projects")

    for enum_name in ["parse_status", "upload_status", "expense_status", "category_type", "project_status"]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
