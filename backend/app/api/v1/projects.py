from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.core.security import ALLOWED_DOCUMENT_EXTENSIONS, generate_safe_filename, validate_file_extension
from app.database import get_db
from app.models.project import BudgetCategory, Project
from app.models.enums import ProjectStatus
from app.schemas.project import (
    BudgetCategoryCreate,
    ExtractedProjectData,
    ProjectCreate,
    ProjectRead,
    ProjectSummary,
    ProjectUpdate,
    ResearcherCreate,
    ResearcherRead,
    ResearcherUpdate,
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

    # Create budget categories — payload 값이 있으면 반영, 없으면 0
    from decimal import Decimal as _Decimal
    from app.models.enums import CategoryType
    budget_map = {
        b.category_type: b.allocated_amount
        for b in (payload.budget_categories or [])
    }
    for cat in CategoryType:
        db.add(BudgetCategory(
            id=uuid.uuid4(),
            project_id=project.id,
            category_type=cat,
            allocated_amount=budget_map.get(cat, _Decimal("0")),
        ))

    await db.flush()
    await db.refresh(project, ["budget_categories"])
    logger.info(
        "project_created",
        project_id=str(project.id),
        code=project.code,
        budget_categories_count=len(budget_map),
    )
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


@router.patch("/{project_id}/metadata")
async def update_project_metadata(
    project_id: uuid.UUID,
    payload: dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """과제 metadata_ JSONB 필드만 단순 업데이트한다."""
    project = await _get_project_or_404(project_id, db)
    project.metadata_ = payload
    flag_modified(project, "metadata_")
    await db.flush()
    logger.info("project_metadata_updated", project_id=str(project_id))
    return {"status": "ok"}


@router.post("/extract-pdf", response_model=ExtractedProjectData)
async def extract_pdf(
    file: UploadFile = File(...),
    doc_type: str = "auto",
) -> ExtractedProjectData:
    """PDF 파일에서 프로젝트 정보를 Claude AI로 추출한다.

    doc_type (쿼리 파라미터):
      - "auto"       : 자동 감지 (기본값, 권장)
      - "plan"       : 사업계획서
      - "agreement"  : 협약체결확약서
      - "researcher" : 참여연구원현황표
    """
    if doc_type not in ("auto", "plan", "agreement", "researcher"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="doc_type은 'auto', 'plan', 'agreement', 'researcher' 중 하나여야 합니다.",
        )

    filename = file.filename or "upload.pdf"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext != "pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDF 파일만 업로드 가능합니다.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="빈 파일입니다.",
        )

    from app.services.project_extractor import extract_project_data

    try:
        raw = await extract_project_data(content, filename, doc_type)
    except Exception as exc:
        logger.error("project_pdf_extract_error", filename=filename, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF 추출 중 오류가 발생했습니다: {exc}",
        ) from exc

    try:
        return ExtractedProjectData(**raw)
    except Exception as exc:
        logger.error("project_pdf_schema_error", filename=filename, error=str(exc), raw=str(raw))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"추출 결과 변환 오류: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# 참여연구원 CRUD
# ---------------------------------------------------------------------------

@router.get("/{project_id}/researchers", response_model=list[ResearcherRead])
async def list_researchers(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list:
    from app.models.project import ProjectResearcher
    from sqlalchemy import select

    await _get_project_or_404(project_id, db)
    result = await db.execute(
        select(ProjectResearcher)
        .where(ProjectResearcher.project_id == project_id)
        .order_by(ProjectResearcher.sort_order)
    )
    return list(result.scalars().all())


@router.post(
    "/{project_id}/researchers",
    response_model=list[ResearcherRead],
    status_code=status.HTTP_201_CREATED,
)
async def upsert_researchers(
    project_id: uuid.UUID,
    payload: list[ResearcherCreate],
    db: AsyncSession = Depends(get_db),
) -> list:
    """참여연구원 목록을 전체 교체한다 (기존 목록 삭제 후 재삽입)."""
    from app.models.project import ProjectResearcher
    from sqlalchemy import delete, select

    await _get_project_or_404(project_id, db)

    # 기존 삭제
    await db.execute(
        delete(ProjectResearcher).where(ProjectResearcher.project_id == project_id)
    )

    # 재삽입
    new_rows = []
    for idx, item in enumerate(payload):
        row = ProjectResearcher(
            id=uuid.uuid4(),
            project_id=project_id,
            personnel_type=item.personnel_type,
            name=item.name,
            position=item.position,
            annual_salary=item.annual_salary,
            monthly_salary=item.monthly_salary,
            participation_months=item.participation_months,
            participation_rate=item.participation_rate,
            cash_amount=item.cash_amount,
            in_kind_amount=item.in_kind_amount,
            sort_order=item.sort_order if item.sort_order is not None else idx,
        )
        db.add(row)
        new_rows.append(row)

    await db.flush()
    for row in new_rows:
        await db.refresh(row)

    logger.info(
        "researchers_upserted",
        project_id=str(project_id),
        count=len(new_rows),
    )
    return new_rows


@router.patch("/{project_id}/researchers/{researcher_id}", response_model=ResearcherRead)
async def update_researcher(
    project_id: uuid.UUID,
    researcher_id: uuid.UUID,
    payload: ResearcherUpdate,
    db: AsyncSession = Depends(get_db),
) -> object:
    from app.models.project import ProjectResearcher
    from sqlalchemy import select

    await _get_project_or_404(project_id, db)
    result = await db.execute(
        select(ProjectResearcher).where(
            ProjectResearcher.id == researcher_id,
            ProjectResearcher.project_id == project_id,
        )
    )
    researcher = result.scalar_one_or_none()
    if not researcher:
        raise HTTPException(status_code=404, detail="연구원을 찾을 수 없습니다.")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(researcher, field, value)

    await db.flush()
    await db.refresh(researcher)
    return researcher


@router.delete(
    "/{project_id}/researchers/{researcher_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_researcher(
    project_id: uuid.UUID,
    researcher_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    from app.models.project import ProjectResearcher

    await _get_project_or_404(project_id, db)
    result = await db.execute(
        select(ProjectResearcher).where(
            ProjectResearcher.id == researcher_id,
            ProjectResearcher.project_id == project_id,
        )
    )
    researcher = result.scalar_one_or_none()
    if not researcher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"참여연구원 ID {researcher_id}를 찾을 수 없습니다.",
        )
    await db.delete(researcher)


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
    from app.config import settings
    safe_name = generate_safe_filename(filename)
    dir_path = os.path.join(settings.storage_dir, "projects", str(project_id))
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, safe_name)
    with open(file_path, "wb") as f:
        f.write(content)
    return file_path
