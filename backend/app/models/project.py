from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import (
    UUID,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
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
