"""Add file_format column to templates

Revision ID: 009
Revises: 008
Create Date: 2026-04-24 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "templates",
        sa.Column("file_format", sa.String(10), nullable=False, server_default="docx"),
    )


def downgrade() -> None:
    op.drop_column("templates", "file_format")
