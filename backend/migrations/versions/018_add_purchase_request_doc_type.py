"""018 add purchase_request to DocumentType enum

Revision ID: 018
Revises: 017
Create Date: 2026-05-06
"""
import sqlalchemy as sa
from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL 12+에서는 ADD VALUE를 트랜잭션 안에서 실행 가능
    op.execute(sa.text("ALTER TYPE document_type ADD VALUE IF NOT EXISTS 'purchase_request'"))


def downgrade() -> None:
    # PostgreSQL은 ENUM 값 제거가 까다로워 no-op
    pass
