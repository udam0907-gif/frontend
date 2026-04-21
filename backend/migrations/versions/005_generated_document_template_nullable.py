"""Make generated_documents.template_id nullable for vendor-based docs

Revision ID: 005
Revises: 004
Create Date: 2026-04-20
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "generated_documents_template_id_fkey",
        "generated_documents",
        type_="foreignkey",
    )
    op.alter_column(
        "generated_documents",
        "template_id",
        existing_type=sa.UUID(),
        nullable=True,
    )
    op.create_foreign_key(
        "generated_documents_template_id_fkey",
        "generated_documents",
        "templates",
        ["template_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "generated_documents_template_id_fkey",
        "generated_documents",
        type_="foreignkey",
    )
    op.alter_column(
        "generated_documents",
        "template_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.create_foreign_key(
        "generated_documents_template_id_fkey",
        "generated_documents",
        "templates",
        ["template_id"],
        ["id"],
        ondelete="RESTRICT",
    )
