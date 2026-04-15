from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.core.security import ALLOWED_DOCUMENT_EXTENSIONS, generate_safe_filename, validate_file_extension
from app.database import get_db
from app.models.project import BudgetCategory, Project
from app.models.enums import ProjectStatus
from app.schemas.project import (
    BudgetCategoryCreate,
    ProjectCreate,
    ProjectRead,
    ProjectSummary,
    ProjectUpdate,
)

router = APIRouter(tags=["projects"])
logger = get_logger(__name__)


@router.get("/", response_model=list[ProjectSummary])
async def list_projects(
    status: ProjectStatus | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[Project]:
    stmt = select(Project)
    if status:
        stmt = stmt.where(Project.status == status)
    stmt = stmt.order_by(Project.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
) -> Project:
    # Check unique code
    existing = await db.execute(
        select(Project).where(Project.code == payload.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"과제 코드 '{payload.code}'가 이미 존재합니다.",
        )

    project = Project(
        id=uuid.uuid4(),
        name=payload.name,
        code=payload.code,
        institution=payload.institution,
        principal_investigator=payload.principal_investigator,
        period_start=payload.period_start,
        period_end=payload.period_end,
        total_budget=payload.total_budget,
        status=payload.status,
        metadata_=payload.metadata_,
    )
    db.add(project)
    await db.flush()

    # Create default budget categories
    from app.models.enums import CategoryType
    for cat in CategoryType:
        db.add(BudgetCategory(
            id=uuid.uuid4(),
            project_id=project.id,
            category_type=cat,
        ))

    await db.flush()
    await db.refresh(project, ["budget_categories"])
    logger.info("project_created", project_id=str(project.id), code=project.code)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Project:
    stmt = (
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.budget_categories))
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"과제 ID {project_id}를 찾을 수 없습니다.",
        )
    return project


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
) -> Project:
    project = await _get_project_or_404(project_id, db)
    update_data = payload.model_dump(exclude_none=True, by_alias=True)

    for field, value in update_data.items():
        attr = "metadata_" if field == "metadata" else field
        setattr(project, attr, value)

    await db.flush()
    await db.refresh(project, ["budget_categories"])
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    project = await _get_project_or_404(project_id, db)
    await db.delete(project)


@router.post("/{project_id}/upload-agreement")
async def upload_agreement(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    project = await _get_project_or_404(project_id, db)
    content = await file.read()
    file_path = await _save_project_file(project_id, file.filename or "agreement", content)
    project.agreement_file_path = file_path
    await db.flush()
    return {"message": "협약서가 업로드되었습니다.", "file_path": file_path}


@router.post("/{project_id}/upload-plan")
async def upload_plan(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    project = await _get_project_or_404(project_id, db)
    content = await file.read()
    file_path = await _save_project_file(project_id, file.filename or "plan", content)
    project.plan_file_path = file_path
    await db.flush()
    return {"message": "사업계획서가 업로드되었습니다.", "file_path": file_path}


@router.get("/{project_id}/stats")
async def get_project_stats(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from app.models.expense import ExpenseItem
    from app.models.enums import ExpenseStatus

    await _get_project_or_404(project_id, db)

    expense_counts = await db.execute(
        select(ExpenseItem.status, func.count(ExpenseItem.id))
        .where(ExpenseItem.project_id == project_id)
        .group_by(ExpenseItem.status)
    )
    counts = {row[0].value: row[1] for row in expense_counts.fetchall()}

    return {
        "project_id": str(project_id),
        "expense_counts_by_status": counts,
        "total_expenses": sum(counts.values()),
    }


async def _get_project_or_404(project_id: uuid.UUID, db: AsyncSession) -> Project:
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"과제 ID {project_id}를 찾을 수 없습니다.",
        )
    return project


async def _save_project_file(
    project_id: uuid.UUID, filename: str, content: bytes
) -> str:
    import os
    from pathlib import Path
    from app.config import settings

    dest_dir = Path(settings.storage_documents_path) / "projects" / str(project_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = generate_safe_filename(filename)
    dest_path = dest_dir / safe_name
    dest_path.write_bytes(content)
    return str(dest_path)
