"""vendor_template_pool 에 cell_map JSONB 컬럼 추가

Revision ID: 014
Revises: 013
Create Date: 2026-04-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vendor_template_pool",
        sa.Column(
            "cell_map",
            postgresql.JSONB,
            nullable=True,
            comment="XlsxCellMapper.analyze() 결과 — 필드명 → 셀 주소 매핑",
        ),
    )


def downgrade() -> None:
    op.drop_column("vendor_template_pool", "cell_map")
