"""017 company_settings employee_count

Revision ID: 017
Revises: 016
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "company_settings",
        sa.Column("employee_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("company_settings", "employee_count")
