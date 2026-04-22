from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel as _BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings as _settings
from app.core.logging import get_logger
from app.database import get_db
from app.models.document import GeneratedDocument
from app.models.expense import ExpenseItem
from app.models.project import Project
from app.models.template import Template
from app.schemas.document import GeneratedDocumentRead, GenerateDocumentRequest
from app.services.document_generator import DocumentGenerator
from app.services.document_set_service import DocumentSetService
from app.services.llm_service import get_llm_service

router = APIRouter(tags=["documents"])
logger = get_logger(__name__)


@router.post("/generate", response_model=GeneratedDocumentRead, status_code=status.HTTP_201_CREATED)
async def generate_document(
    payload: GenerateDocumentRequest,
    db: AsyncSession = Depends(get_db),
) -> GeneratedDocument:
    # Fetch expense item with project
    expense_result = await db.execute(
        select(ExpenseItem)
        .where(ExpenseItem.id == payload.expense_item_id)
        .options(selectinload(ExpenseItem.documents))
    )
    expense = expense_result.scalar_one_or_none()
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="지출 항목을 찾을 수 없습니다.",
        )

    # Fetch template
    template_result = await db.execute(
        select(Template).where(
            Template.id == payload.template_id,
            Template.is_active == True,
        )
    )
    template = template_result.scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="활성화된 템플릿을 찾을 수 없습니다.",
        )

    # Fetch project data
    project_result = await db.execute(
        select(Project).where(Project.id == expense.project_id)
    )
    project = project_result.scalar_one_or_none()

    project_data: dict[str, Any] = {}
    if project:
        project_data = {
            "project_name": project.name,
            "project_code": project.code,
            "institution": project.institution,
            "pi_name": project.principal_investigator,
            "period_start": str(project.period_start),
            "period_end": str(project.period_end),
        }

    llm_service = get_llm_service()
    generator = DocumentGenerator(llm_service)

    result = await generator.generate(
        template_path=template.file_path,
        field_map=template.field_map,
        user_values=payload.field_values,
        project_data=project_data,
        expense_item_id=str(payload.expense_item_id),
        template_id=str(payload.template_id),
    )

    gen_doc = GeneratedDocument(
        id=uuid.uuid4(),
        expense_item_id=payload.expense_item_id,
        template_id=payload.template_id,
        output_path=result["output_path"],
        generation_trace=result["generation_trace"],
        is_valid=result["generation_trace"].get("validation_passed", False),
    )
    db.add(gen_doc)
    await db.flush()
    await db.refresh(gen_doc)
    return gen_doc


@router.get("/expense/{expense_id}", response_model=list[GeneratedDocumentRead])
async def list_generated_documents(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[GeneratedDocument]:
    result = await db.execute(
        select(GeneratedDocument).where(GeneratedDocument.expense_item_id == expense_id)
    )
    return list(result.scalars().all())


@router.get("/{document_id}/download")
async def download_generated_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    result = await db.execute(
        select(GeneratedDocument).where(GeneratedDocument.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="생성된 문서를 찾을 수 없습니다.",
        )
    file_path = Path(doc.output_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="파일을 찾을 수 없습니다.",
        )
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream",
    )


@router.get("/{document_id}", response_model=GeneratedDocumentRead)
async def get_generated_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> GeneratedDocument:
    result = await db.execute(
        select(GeneratedDocument).where(GeneratedDocument.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="생성된 문서를 찾을 수 없습니다.",
        )
    return doc


# ─── Document Set ─────────────────────────────────────────────────────────────


class DocumentSetResponse(_BaseModel):
    expense_item_id: str
    category_type: str
    total: int
    generated: int
    errors: int
    all_generated: bool
    items: list[dict]


@router.post("/generate-set/{expense_id}", response_model=DocumentSetResponse)
async def generate_document_set(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DocumentSetResponse:
    """
    비목별 문서세트 전체 생성.
    - 원본 양식에 값 정확 매핑 (AI 생성 금지)
    - 비교견적서: 원금액 × 1.1 자동 적용
    - 업체 파일: 업체 등록 파일에서 직접 복사
    """
    svc = DocumentSetService(_settings.storage_documents_path)
    try:
        result = await svc.generate_set(expense_id, db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    return DocumentSetResponse(
        expense_item_id=str(result.expense_item_id),
        category_type=result.category_type.value,
        total=len(result.items),
        generated=result.generated_count,
        errors=result.error_count,
        all_generated=result.all_generated,
        items=[
            {
                "document_type": i.document_type.value,
                "status": i.status,
                "output_path": i.output_path,
                "generated_document_id": str(i.generated_document_id) if i.generated_document_id else None,
                "error_message": i.error_message,
                "is_vendor_doc": i.is_vendor_doc,
            }
            for i in result.items
        ],
    )


@router.get("/latest-set/{expense_id}")
async def get_latest_document_set(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """최근 생성된 문서세트 조회 (페이지 로드 시 기존 결과 표시용)"""
    expense_r = await db.execute(
        select(ExpenseItem).where(ExpenseItem.id == expense_id)
    )
    expense = expense_r.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="지출 항목을 찾을 수 없습니다.")

    r = await db.execute(
        select(GeneratedDocument)
        .where(GeneratedDocument.expense_item_id == expense_id)
        .order_by(GeneratedDocument.created_at.desc())
    )
    all_docs = list(r.scalars().all())

    if not all_docs:
        return {
            "expense_item_id": str(expense_id),
            "category_type": expense.category_type.value,
            "total": 0,
            "generated": 0,
            "errors": 0,
            "all_generated": True,
            "items": [],
        }

    # batch_id로 최신 배치 그룹핑 (없으면 5초 윈도우 fallback)
    latest_trace = all_docs[0].generation_trace or {}
    latest_batch_id = latest_trace.get("batch_id")
    if latest_batch_id:
        batch = [d for d in all_docs if (d.generation_trace or {}).get("batch_id") == latest_batch_id]
    else:
        latest_ts = all_docs[0].created_at
        batch = [d for d in all_docs if abs((latest_ts - d.created_at).total_seconds()) < 5]

    status_map = {
        "excel_rendered":            "excel_rendered",
        "docx_rendered":             "excel_rendered",
        "vendor_attachment_included":"vendor_attachment_included",
        "mapping_needed":            "mapping_needed",
        "render_failed":             "render_failed",
    }

    items = []
    for doc in batch:
        trace = doc.generation_trace or {}
        items.append({
            "document_type": trace.get("document_type", "unknown"),
            "status": status_map.get(trace.get("render_mode", ""), "generated"),
            "output_path": doc.output_path,
            "generated_document_id": str(doc.id),
            "error_message": None,
            "is_vendor_doc": trace.get("render_mode") == "vendor_attachment_included",
        })

    _ok   = {"excel_rendered", "vendor_attachment_included", "mapping_needed"}
    _err  = {"render_failed", "template_missing", "vendor_file_missing"}
    gen   = sum(1 for i in items if i["status"] in _ok)
    errs  = sum(1 for i in items if i["status"] in _err)

    return {
        "expense_item_id": str(expense_id),
        "category_type": expense.category_type.value,
        "total": len(items),
        "generated": gen,
        "errors": errs,
        "all_generated": errs == 0,
        "items": items,
    }


@router.get("/set-status/{expense_id}")
async def get_document_set_status(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    r = await db.execute(
        select(GeneratedDocument)
        .where(GeneratedDocument.expense_item_id == expense_id)
        .order_by(GeneratedDocument.created_at.desc())
    )
    docs = r.scalars().all()
    return {
        "expense_item_id": str(expense_id),
        "total_generated": len(docs),
        "documents": [
            {
                "id": str(d.id),
                "template_id": str(d.template_id) if d.template_id else None,
                "output_path": d.output_path,
                "is_valid": d.is_valid,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ],
    }
