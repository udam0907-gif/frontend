"""Add vendor_category, drop vendor_type, add templates.project_id

Revision ID: 004
Revises: 003
Create Date: 2026-04-20
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # vendors: replace vendor_type enum with vendor_category string
    op.add_column("vendors", sa.Column("vendor_category", sa.String(20), nullable=True))
    op.execute("UPDATE vendors SET vendor_category = '매입처'")
    op.alter_column("vendors", "vendor_category", nullable=False)
    op.drop_column("vendors", "vendor_type")

    # templates: add project_id FK (was part of 003 but never ran)
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

    op.add_column(
        "vendors",
        sa.Column(
            "vendor_type",
            sa.Enum(
                "outsourcing", "labor", "test_report", "materials", "meeting", "other",
                name="category_type",
                create_type=False,
            ),
            nullable=True,
        ),
    )
    op.execute("UPDATE vendors SET vendor_type = 'materials'")
    op.alter_column("vendors", "vendor_type", nullable=False)
    op.drop_column("vendors", "vendor_category")
