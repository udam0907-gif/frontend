"""vendors: project_id nullable (전역 업체 관리)

Revision ID: 012
Revises: 011
Create Date: 2026-04-29
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # FK 제약 삭제 후 nullable=True로 변경
    with op.batch_alter_table("vendors") as batch_op:
        batch_op.drop_constraint("vendors_project_id_fkey", type_="foreignkey")
        batch_op.alter_column("project_id", existing_type=sa.UUID(), nullable=True)
        batch_op.create_foreign_key(
            "vendors_project_id_fkey",
            "projects",
            ["project_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("vendors") as batch_op:
        batch_op.drop_constraint("vendors_project_id_fkey", type_="foreignkey")
        batch_op.alter_column("project_id", existing_type=sa.UUID(), nullable=False)
        batch_op.create_foreign_key(
            "vendors_project_id_fkey",
            "projects",
            ["project_id"],
            ["id"],
            ondelete="CASCADE",
        )
