"""vendor_template_pool 테이블에 transaction_cell_map 컬럼 추가

Revision ID: 016
Revises: 015
Create Date: 2026-05-06
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vendor_template_pool",
        sa.Column("transaction_cell_map", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("vendor_template_pool", "transaction_cell_map")
