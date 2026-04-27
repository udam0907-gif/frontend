from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import (
    UUID,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models.mixins import TimestampMixin
from app.models.enums import CategoryType, ProjectStatus


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    institution: Mapped[str] = mapped_column(String(255), nullable=False)
    principal_investigator: Mapped[str] = mapped_column(String(100), nullable=False)
    period_start: Mapped[Date] = mapped_column(Date, nullable=False)
    period_end: Mapped[Date] = mapped_column(Date, nullable=False)
    total_budget: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2), nullable=False
    )
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status"),
        nullable=False,
        default=ProjectStatus.active,
    )
    agreement_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )

    budget_categories: Mapped[list[BudgetCategory]] = relationship(
        "BudgetCategory", back_populates="project", cascade="all, delete-orphan"
    )
    expense_items: Mapped[list] = relationship(
        "ExpenseItem", back_populates="project", cascade="all, delete-orphan"
    )
    researchers: Mapped[list[ProjectResearcher]] = relationship(
        "ProjectResearcher", back_populates="project", cascade="all, delete-orphan",
        order_by="ProjectResearcher.sort_order",
    )

    __table_args__ = (
        CheckConstraint("period_end > period_start", name="ck_project_period"),
        CheckConstraint("total_budget > 0", name="ck_project_budget_positive"),
    )


class BudgetCategory(Base, TimestampMixin):
    __tablename__ = "budget_categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_type: Mapped[CategoryType] = mapped_column(
        Enum(CategoryType, name="category_type"), nullable=False
    )
    allocated_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2), nullable=False, default=Decimal("0")
    )
    spent_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2), nullable=False, default=Decimal("0")
    )

    project: Mapped[Project] = relationship("Project", back_populates="budget_categories")

    __table_args__ = (
        UniqueConstraint("project_id", "category_type", name="uq_budget_category"),
        CheckConstraint("allocated_amount >= 0", name="ck_budget_allocated_non_negative"),
        CheckConstraint("spent_amount >= 0", name="ck_budget_spent_non_negative"),
    )


class ProjectResearcher(Base, TimestampMixin):
    __tablename__ = "project_researchers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    personnel_type: Mapped[str] = mapped_column(
        String(10), nullable=False, default="기존"
    )  # "기존" | "신규"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    annual_salary: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=18, scale=2), nullable=True
    )  # 연봉 (천원)
    monthly_salary: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=18, scale=2), nullable=True
    )  # 월급여 (천원)
    participation_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    participation_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=5, scale=2), nullable=True
    )  # 참여율 (%)
    cash_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=18, scale=2), nullable=True
    )  # 현금 합계 (천원)
    in_kind_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=18, scale=2), nullable=True
    )  # 현물 합계 (천원)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    project: Mapped[Project] = relationship("Project", back_populates="researchers")
