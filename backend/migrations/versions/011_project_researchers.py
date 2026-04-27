"""project_researchers table

Revision ID: 011
Revises: 010
Create Date: 2026-04-27 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_researchers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("personnel_type", sa.String(10), nullable=False, server_default="기존"),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("position", sa.String(100), nullable=True),
        sa.Column("annual_salary", sa.Numeric(18, 2), nullable=True),
        sa.Column("monthly_salary", sa.Numeric(18, 2), nullable=True),
        sa.Column("participation_months", sa.Integer, nullable=True),
        sa.Column("participation_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("cash_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("in_kind_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_project_researchers_project_id",
        "project_researchers",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_researchers_project_id", table_name="project_researchers")
    op.drop_table("project_researchers")
