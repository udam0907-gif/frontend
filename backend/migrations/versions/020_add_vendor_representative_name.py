"""add representative_name to vendors

Revision ID: 020
Revises: 019
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vendors",
        sa.Column("representative_name", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("vendors", "representative_name")
