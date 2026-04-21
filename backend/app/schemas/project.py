from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import CategoryType, ProjectStatus


class BudgetCategoryCreate(BaseModel):
    category_type: CategoryType
    allocated_amount: Decimal = Field(ge=0)


class BudgetCategoryRead(BudgetCategoryCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    spent_amount: Decimal
    created_at: datetime
    updated_at: datetime


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=100)
    institution: str = Field(min_length=1, max_length=255)
    principal_investigator: str = Field(min_length=1, max_length=100)
    period_start: date
    period_end: date
    total_budget: Decimal = Field(gt=0)
    status: ProjectStatus = ProjectStatus.active
    metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata")

    @field_validator("period_end")
    @classmethod
    def end_after_start(cls, v: date, info: Any) -> date:
        if "period_start" in info.data and v <= info.data["period_start"]:
            raise ValueError("종료일은 시작일보다 이후여야 합니다.")
        return v

    model_config = ConfigDict(populate_by_name=True)


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    institution: str | None = None
    principal_investigator: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    total_budget: Decimal | None = Field(None, gt=0)
    status: ProjectStatus | None = None
    metadata_: dict[str, Any] | None = Field(None, alias="metadata")

    model_config = ConfigDict(populate_by_name=True)


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str
    institution: str
    principal_investigator: str
    period_start: date
    period_end: date
    total_budget: Decimal
    status: ProjectStatus
    agreement_file_path: str | None
    plan_file_path: str | None
    metadata_: dict[str, Any] = Field(alias="metadata_")
    created_at: datetime
    updated_at: datetime
    budget_categories: list[BudgetCategoryRead] = []


class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str
    institution: str
    status: ProjectStatus
    period_start: date
    period_end: date
    total_budget: Decimal
