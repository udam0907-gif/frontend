"""add address/business_type/business_item to vendors

Revision ID: 021
Revises: 020
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vendors", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("vendors", sa.Column("business_type", sa.String(length=100), nullable=True))
    op.add_column("vendors", sa.Column("business_item", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("vendors", "business_item")
    op.drop_column("vendors", "business_type")
    op.drop_column("vendors", "address")
