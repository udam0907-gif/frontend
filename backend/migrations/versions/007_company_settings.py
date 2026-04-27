"""Add company settings table for top-level company defaults

Revision ID: 007
Revises: 006
Create Date: 2026-04-22
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", sa.String(length=100), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("company_registration_number", sa.String(length=50), nullable=True),
        sa.Column("representative_name", sa.String(length=100), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("business_type", sa.String(length=255), nullable=True),
        sa.Column("business_item", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("fax", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("default_manager_name", sa.String(length=100), nullable=True),
        sa.Column("seal_image_path", sa.Text(), nullable=True),
        sa.Column("company_business_registration_path", sa.Text(), nullable=True),
        sa.Column("company_bank_copy_path", sa.Text(), nullable=True),
        sa.Column("company_quote_template_path", sa.Text(), nullable=True),
        sa.Column("company_transaction_statement_template_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id"),
    )
    op.create_index(op.f("ix_company_settings_company_id"), "company_settings", ["company_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_company_settings_company_id"), table_name="company_settings")
    op.drop_table("company_settings")
