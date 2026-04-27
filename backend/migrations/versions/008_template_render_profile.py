"""Add render_profile column to templates for quote-level rendering strategy

Revision ID: 008
Revises: 007
Create Date: 2026-04-24
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "templates",
        sa.Column("render_profile", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("templates", "render_profile")
