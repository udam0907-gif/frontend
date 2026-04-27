"""vendor_template_pool and company_vendor_template

Revision ID: 010
Revises: 009
Create Date: 2026-04-24 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vendor_template_pool",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "vendor_business_number",
            sa.String(20),
            nullable=False,
            unique=True,
            comment="사업자등록번호 XXX-XX-XXXXX (고유 키)",
        ),
        sa.Column("vendor_name", sa.String(255), nullable=False, comment="업체명 (표시용)"),
        sa.Column(
            "file_format",
            sa.String(10),
            nullable=False,
            server_default="xlsx",
            comment="xls | xlsx | docx",
        ),
        sa.Column(
            "layout_map",
            postgresql.JSONB,
            nullable=False,
            server_default="{}",
            comment="분석된 서식 구조 메타데이터",
        ),
        sa.Column(
            "render_profile",
            postgresql.JSONB,
            nullable=False,
            server_default="{}",
            comment="렌더링 전략 (엔진, 채움 방식)",
        ),
        sa.Column(
            "field_map",
            postgresql.JSONB,
            nullable=False,
            server_default="{}",
            comment="placeholder → 필드 메타데이터",
        ),
        sa.Column("verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "verified_count",
            sa.Integer,
            nullable=False,
            server_default="0",
            comment="이 풀을 사용하는 고객사 수",
        ),
        sa.Column(
            "sample_file_path",
            sa.Text,
            nullable=True,
            comment="분석에 사용된 샘플 파일 경로 (운영 참고용)",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index(
        "ix_vendor_template_pool_biznum",
        "vendor_template_pool",
        ["vendor_business_number"],
        unique=True,
    )

    op.create_table(
        "company_vendor_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="고객사 ID (멀티테넌트 격리)",
        ),
        sa.Column(
            "pool_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vendor_template_pool.id", ondelete="RESTRICT"),
            nullable=False,
            comment="공유 풀 참조",
        ),
        sa.Column("vendor_alias", sa.String(255), nullable=True, comment="고객사가 쓰는 업체 별칭"),
        sa.Column(
            "custom_override",
            postgresql.JSONB,
            nullable=False,
            server_default="{}",
            comment="고객사가 덮어쓴 field_map 부분",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "pool_id", name="uq_company_vendor_template"),
    )

    op.create_index(
        "ix_company_vendor_templates_company",
        "company_vendor_templates",
        ["company_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_company_vendor_templates_company")
    op.drop_table("company_vendor_templates")
    op.drop_index("ix_vendor_template_pool_biznum")
    op.drop_table("vendor_template_pool")
