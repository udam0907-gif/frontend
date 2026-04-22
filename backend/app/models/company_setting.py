from __future__ import annotations

import uuid

from sqlalchemy import UUID, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class CompanySetting(Base, TimestampMixin):
    __tablename__ = "company_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True, default="default"
    )

    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_registration_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    representative_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_item: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fax: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    default_manager_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    seal_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    company_business_registration_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_bank_copy_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_quote_template_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_transaction_statement_template_path: Mapped[str | None] = mapped_column(Text, nullable=True)
