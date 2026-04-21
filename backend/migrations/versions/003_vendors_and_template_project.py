"""Add vendors table and template.project_id

Revision ID: 003
Revises: 002
Create Date: 2026-04-20
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vendors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("vendor_category", sa.String(20), nullable=False),
        sa.Column("business_number", sa.String(20), nullable=False),
        sa.Column("contact", sa.String(100), nullable=True),
        sa.Column("business_registration_path", sa.Text, nullable=True),
        sa.Column("bank_copy_path", sa.Text, nullable=True),
        sa.Column("quote_template_path", sa.Text, nullable=True),
        sa.Column("transaction_statement_path", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_vendors_project_id", "vendors", ["project_id"])

    op.add_column(
        "templates",
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_templates_project_id", "templates", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_templates_project_id", table_name="templates")
    op.drop_column("templates", "project_id")
    op.drop_index("ix_vendors_project_id", table_name="vendors")
    op.drop_table("vendors")
