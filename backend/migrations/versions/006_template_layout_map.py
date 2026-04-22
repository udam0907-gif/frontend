"""Add layout_map column to templates for structured field mapping

Revision ID: 006
Revises: 005
Create Date: 2026-04-22
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "templates",
        sa.Column("layout_map", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("templates", "layout_map")
