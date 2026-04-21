from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database import get_db
from app.models.enums import CategoryType, DocumentType
from app.models.template import Template
from app.schemas.template import TemplateRead, TemplateUpdate
from app.services.template_service import TemplateService

router = APIRouter(tags=["templates"])
logger = get_logger(__name__)
_template_service = TemplateService()


@router.get("/", response_model=list[TemplateRead])
async def list_templates(
    category_type: CategoryType | None = None,
    document_type: DocumentType | None = None,
    active_only: bool = True,
    project_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[Template]:
    stmt = select(Template)
    if category_type:
        stmt = stmt.where(Template.category_type == category_type)
    if document_type:
        stmt = stmt.where(Template.document_type == document_type)
    if active_only:
        stmt = stmt.where(Template.is_active == True)
    if project_id is not None:
        stmt = stmt.where(Template.project_id == project_id)
    stmt = stmt.order_by(Template.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/", response_model=TemplateRead, status_code=status.HTTP_201_CREATED)
async def upload_template(
    name: str = Form(...),
    category_type: CategoryType = Form(...),
    document_type: DocumentType = Form(...),
    version: str = Form("1.0.0"),
    description: str | None = Form(None),
    project_id: uuid.UUID | None = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> Template:
    content = await file.read()
    original_filename = file.filename or "template"

    _template_service.validate_file(original_filename, content)
    safe_filename, file_path = _template_service.save_file(original_filename, content)
    field_map = _template_service.extract_placeholders(file_path)

    template = Template(
        id=uuid.uuid4(),
        name=name,
        category_type=category_type,
        document_type=document_type,
        filename=safe_filename,
        file_path=file_path,
        version=version,
        field_map=field_map,
        is_active=True,
        description=description,
        project_id=project_id,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)

    logger.info(
        "template_uploaded",
        template_id=str(template.id),
        category=category_type.value,
        doc_type=document_type.value,
        placeholders=len(field_map),
    )
    return template


@router.get("/{template_id}", response_model=TemplateRead)
async def get_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Template:
    template = await _get_or_404(template_id, db)
    return template


@router.patch("/{template_id}", response_model=TemplateRead)
async def update_template(
    template_id: uuid.UUID,
    payload: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
) -> Template:
    template = await _get_or_404(template_id, db)
    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(template, field, value)
    await db.flush()
    await db.refresh(template)
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    template = await _get_or_404(template_id, db)
    _template_service.delete_file(template.file_path)
    await db.delete(template)


@router.get("/{template_id}/fields")
async def get_template_fields(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    template = await _get_or_404(template_id, db)
    return {
        "template_id": str(template.id),
        "template_name": template.name,
        "field_map": template.field_map,
    }


async def _get_or_404(template_id: uuid.UUID, db: AsyncSession) -> Template:
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"템플릿 ID {template_id}를 찾을 수 없습니다.",
        )
    return template
