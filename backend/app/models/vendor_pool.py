from __future__ import annotations

import uuid

from sqlalchemy import UUID, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin


class VendorTemplatePool(Base, TimestampMixin):
    """
    업체 양식 공유 풀.
    사업자번호로 업체를 식별하고 layout_map을 전체 고객사가 공유한다.
    고객사는 읽기만 가능. 수정은 시스템/관리자만.
    """

    __tablename__ = "vendor_template_pool"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_business_number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    vendor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_format: Mapped[str] = mapped_column(String(10), nullable=False, default="xlsx")
    layout_map: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    render_profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    field_map: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verified_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sample_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    company_templates: Mapped[list[CompanyVendorTemplate]] = relationship(
        "CompanyVendorTemplate", back_populates="pool", cascade="all, delete-orphan"
    )


class CompanyVendorTemplate(Base, TimestampMixin):
    """
    고객사별 업체 템플릿 연결.
    공유 풀을 참조하고 고객사가 커스텀한 부분만 custom_override에 저장.
    company_id 없이는 절대 접근 불가.
    """

    __tablename__ = "company_vendor_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    pool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vendor_template_pool.id", ondelete="RESTRICT"),
        nullable=False,
    )
    vendor_alias: Mapped[str | None] = mapped_column(String(255), nullable=True)
    custom_override: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    pool: Mapped[VendorTemplatePool] = relationship(
        "VendorTemplatePool", back_populates="company_templates"
    )
