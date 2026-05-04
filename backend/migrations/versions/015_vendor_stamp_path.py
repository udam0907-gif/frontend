"""vendors 테이블에 stamp_path 컬럼 추가 (직인 이미지 경로)

Revision ID: 015
Revises: 014
Create Date: 2026-05-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vendors",
        sa.Column("stamp_path", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("vendors", "stamp_path")
