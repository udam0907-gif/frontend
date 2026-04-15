from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.database import get_db
from app.models.document import GeneratedDocument
from app.models.expense import ExpenseItem
from app.models.project import Project
from app.models.template import Template
from app.schemas.document import GeneratedDocumentRead, GenerateDocumentRequest
from app.services.document_generator import DocumentGenerator
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
