"""document_set_specs 테이블 신설 + CategoryType enum 확장 + category_payload 컬럼

Revision ID: 013
Revises: 012
Create Date: 2026-04-29
"""
from __future__ import annotations

import json
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.data.document_set_seeds import DOCUMENT_SET_SEEDS

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None

_DEFAULT_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png", ".xlsx", ".docx"]


def upgrade() -> None:
    # 1) CategoryType enum 3종 추가
    # Postgres enum ADD VALUE는 트랜잭션 외부에서 실행해야 하므로 execute 방식 사용
    op.execute("ALTER TYPE category_type ADD VALUE IF NOT EXISTS 'research_activity'")
    op.execute("ALTER TYPE category_type ADD VALUE IF NOT EXISTS 'indirect_credit'")
    op.execute("ALTER TYPE category_type ADD VALUE IF NOT EXISTS 'entrusted_audit'")

    # 2) document_set_specs 테이블 생성
    # server_default에서 ::jsonb 캐스트를 피하고 text() 없이 직접 처리
    op.create_table(
        "document_set_specs",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("doc_kind", sa.String(100), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("template_path", sa.String(500), nullable=True),
        sa.Column("upload_hint", sa.Text(), nullable=True),
        sa.Column("allowed_extensions", JSONB, nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("category", "doc_kind", name="uq_doc_set_specs_cat_kind"),
    )

    # 3) 인덱스 생성
    op.create_index("ix_document_set_specs_category", "document_set_specs", ["category"])
    op.create_index(
        "ix_document_set_specs_category_sort_order",
        "document_set_specs",
        ["category", "sort_order"],
    )

    # 4) expense_items.category_payload JSONB nullable 컬럼 추가
    op.add_column(
        "expense_items",
        sa.Column("category_payload", JSONB, nullable=True),
    )

    # 5) 시드 데이터 INSERT — ON CONFLICT (category, doc_kind) DO NOTHING (idempotent)
    # asyncpg는 ::jsonb 캐스트 불가 → JSON 문자열을 text 파라미터로 넘기고 DB에서 캐스트
    conn = op.get_bind()
    extensions_json = json.dumps(_DEFAULT_EXTENSIONS)
    for seed in DOCUMENT_SET_SEEDS:
        conn.execute(
            sa.text(
                "INSERT INTO document_set_specs "
                "(id, category, doc_kind, source, is_required, template_path, upload_hint, allowed_extensions, sort_order) "
                "VALUES (:id, :category, :doc_kind, :source, :is_required, :template_path, :upload_hint, "
                "        cast(:allowed_extensions as jsonb), :sort_order) "
                "ON CONFLICT (category, doc_kind) DO NOTHING"
            ),
            {
                "id": str(uuid.uuid4()),
                "category": seed["category"],
                "doc_kind": seed["doc_kind"],
                "source": seed["source"],
                "is_required": seed["is_required"],
                "template_path": seed.get("template_path"),
                "upload_hint": seed.get("upload_hint"),
                "allowed_extensions": extensions_json,
                "sort_order": seed["sort_order"],
            },
        )


def downgrade() -> None:
    # 시드 데이터 삭제
    op.execute("DELETE FROM document_set_specs")

    # document_set_specs 테이블 DROP
    op.drop_index("ix_document_set_specs_category_sort_order", table_name="document_set_specs")
    op.drop_index("ix_document_set_specs_category", table_name="document_set_specs")
    op.drop_table("document_set_specs")

    # expense_items.category_payload 컬럼 DROP
    op.drop_column("expense_items", "category_payload")

    # NOTE: Postgres enum 값 제거(research_activity, indirect_credit, entrusted_audit)는
    # 자동 downgrade 불가 — 수동으로 아래 SQL을 직접 실행해야 합니다.
    # ALTER TYPE category_type RENAME TO category_type_old;
    # CREATE TYPE category_type AS ENUM ('outsourcing','labor','test_report','materials','meeting','other');
    # ALTER TABLE expense_items ALTER COLUMN category_type TYPE category_type USING category_type::text::category_type;
    # DROP TYPE category_type_old;
