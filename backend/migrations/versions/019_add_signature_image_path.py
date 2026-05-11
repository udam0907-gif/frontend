"""019 add signature_image_path to company_settings

Revision ID: 019
Revises: 018
Create Date: 2026-05-11
"""
import sqlalchemy as sa
from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "company_settings",
        sa.Column("signature_image_path", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("company_settings", "signature_image_path")
