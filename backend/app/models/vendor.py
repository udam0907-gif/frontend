from __future__ import annotations

import uuid

from sqlalchemy import UUID, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class Vendor(Base, TimestampMixin):
    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    representative_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    business_item: Mapped[str | None] = mapped_column(String(200), nullable=True)
    vendor_category: Mapped[str] = mapped_column(String(20), nullable=False)  # "매입처" | "매출처"
    business_number: Mapped[str] = mapped_column(String(20), nullable=False)
    contact: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # 첨부 파일 경로
    business_registration_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_copy_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    quote_template_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    transaction_statement_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    stamp_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
