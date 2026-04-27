from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.core.security import ALLOWED_DOCUMENT_EXTENSIONS, generate_safe_filename, validate_file_extension
from app.config import settings
from app.database import get_db
from app.models.document import GeneratedDocument
from app.models.enums import CategoryType, DocumentType, ExpenseStatus, UploadStatus
from app.models.expense import ExpenseDocument, ExpenseItem
from app.schemas.expense import (
    ExpenseDocumentRead,
    ExpenseItemCreate,
    ExpenseItemRead,
    ExpenseItemUpdate,
)

router = APIRouter(tags=["expenses"])
logger = get_logger(__name__)


@router.get("/", response_model=list[ExpenseItemRead])
async def list_expenses(
    project_id: uuid.UUID | None = None,
    status: ExpenseStatus | None = None,
    category_type: CategoryType | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[ExpenseItem]:
    stmt = select(ExpenseItem).options(selectinload(ExpenseItem.documents))
    if project_id:
        stmt = stmt.where(ExpenseItem.project_id == project_id)
    if status:
        stmt = stmt.where(ExpenseItem.status == status)
    if category_type:
        stmt = stmt.where(ExpenseItem.category_type == category_type)
    stmt = stmt.order_by(ExpenseItem.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/", response_model=ExpenseItemRead, status_code=status.HTTP_201_CREATED)
async def create_expense(
    payload: ExpenseItemCreate,
    db: AsyncSession = Depends(get_db),
) -> ExpenseItem:
    # Verify project exists
    from app.models.project import Project
    proj = await db.execute(
        select(Project).where(Project.id == payload.project_id)
    )
    if not proj.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"과제 ID {payload.project_id}를 찾을 수 없습니다.",
        )

    expense = ExpenseItem(
        id=uuid.uuid4(),
        project_id=payload.project_id,
        category_type=payload.category_type,
        title=payload.title,
        description=payload.description,
        amount=payload.amount,
        expense_date=payload.expense_date,
        vendor_name=payload.vendor_name,
        vendor_registration_number=payload.vendor_registration_number,
        metadata_=payload.metadata_,
        status=ExpenseStatus.draft,
    )
    db.add(expense)
    await db.flush()
    await db.refresh(expense, ["documents"])
    logger.info("expense_created", expense_id=str(expense.id), category=payload.category_type.value)
    return expense


@router.get("/{expense_id}", response_model=ExpenseItemRead)
async def get_expense(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ExpenseItem:
    return await _get_expense_or_404(expense_id, db)


@router.patch("/{expense_id}", response_model=ExpenseItemRead)
async def update_expense(
    expense_id: uuid.UUID,
    payload: ExpenseItemUpdate,
    db: AsyncSession = Depends(get_db),
) -> ExpenseItem:
    expense = await _get_expense_or_404(expense_id, db)
    update_data = payload.model_dump(exclude_none=True, by_alias=True)
    metadata_changed = "metadata" in update_data
    for field, value in update_data.items():
        attr = "metadata_" if field == "metadata" else field
        setattr(expense, attr, value)
    # metadata(업체/비교견적 등) 변경 시 기존 생성 문서 삭제 → 재생성 강제
    if metadata_changed:
        stale_docs = await db.execute(
            select(GeneratedDocument).where(GeneratedDocument.expense_item_id == expense_id)
        )
        for doc in stale_docs.scalars().all():
            await db.delete(doc)
        logger.info("generated_docs_cleared_on_metadata_update", expense_id=str(expense_id))
    await db.flush()
    # db.delete 후 expire된 속성(updated_at 등) 때문에 MissingGreenlet 방지: 재조회
    refreshed = await db.execute(
        select(ExpenseItem)
        .where(ExpenseItem.id == expense_id)
        .options(selectinload(ExpenseItem.documents))
    )
    return refreshed.scalar_one()


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_expense(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    expense = await _get_expense_or_404(expense_id, db)
    await db.delete(expense)


@router.post("/{expense_id}/documents", response_model=ExpenseDocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    expense_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> ExpenseDocument:
    await _get_expense_or_404(expense_id, db)

    original_filename = file.filename or "document"
    if not validate_file_extension(original_filename, ALLOWED_DOCUMENT_EXTENSIONS):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"허용되지 않는 파일 형식입니다. 허용: {ALLOWED_DOCUMENT_EXTENSIONS}",
        )

    if document_type == DocumentType.inspection_photos and Path(original_filename).suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="검수 이미지는 JPG, JPEG, PNG 형식만 업로드할 수 있습니다.",
        )

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="파일 크기는 50MB를 초과할 수 없습니다.",
        )

    dest_dir = Path(settings.storage_documents_path) / "expenses" / str(expense_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = generate_safe_filename(original_filename)
    file_path = str(dest_dir / safe_name)

    if document_type == DocumentType.inspection_photos:
        existing_docs = await db.execute(
            select(ExpenseDocument).where(
                ExpenseDocument.expense_item_id == expense_id,
                ExpenseDocument.document_type == document_type,
            )
        )
        for existing in existing_docs.scalars().all():
            try:
                Path(existing.file_path).unlink(missing_ok=True)
            except OSError:
                pass
            await db.delete(existing)

    Path(file_path).write_bytes(content)

    doc = ExpenseDocument(
        id=uuid.uuid4(),
        expense_item_id=expense_id,
        document_type=document_type,
        filename=original_filename,
        file_path=file_path,
        file_size=len(content),
        mime_type=file.content_type,
        upload_status=UploadStatus.uploaded,
        extracted_data={},
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    doc_id = doc.id
    background_tasks.add_task(
        _extract_document_data_background,
        doc_id,
        file_path,
        original_filename,
    )

    logger.info(
        "expense_document_uploaded",
        expense_id=str(expense_id),
        doc_type=document_type.value,
        size=len(content),
    )
    return doc


@router.get("/{expense_id}/documents", response_model=list[ExpenseDocumentRead])
async def list_expense_documents(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ExpenseDocument]:
    await _get_expense_or_404(expense_id, db)
    result = await db.execute(
        select(ExpenseDocument).where(ExpenseDocument.expense_item_id == expense_id)
    )
    return list(result.scalars().all())


@router.delete("/{expense_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_expense_document(
    expense_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(ExpenseDocument).where(
            ExpenseDocument.id == document_id,
            ExpenseDocument.expense_item_id == expense_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="서류를 찾을 수 없습니다.",
        )
    try:
        Path(doc.file_path).unlink(missing_ok=True)
    except OSError:
        pass
    await db.delete(doc)


async def _extract_document_data_background(
    document_id: uuid.UUID,
    file_path: str,
    filename: str,
) -> None:
    from app.database import AsyncSessionLocal
    from app.services.document_extractor_service import DocumentExtractorService

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(ExpenseDocument).where(ExpenseDocument.id == document_id)
            )
            doc = result.scalar_one_or_none()
            if not doc:
                return
            extractor = DocumentExtractorService()
            doc.extracted_data = extractor.extract(file_path, filename)
            await db.commit()
            logger.info("document_extraction_completed", document_id=str(document_id))
        except Exception as e:
            logger.error("document_extraction_failed", document_id=str(document_id), error=str(e))


async def _get_expense_or_404(expense_id: uuid.UUID, db: AsyncSession) -> ExpenseItem:
    result = await db.execute(
        select(ExpenseItem)
        .where(ExpenseItem.id == expense_id)
        .options(selectinload(ExpenseItem.documents))
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"지출 항목 ID {expense_id}를 찾을 수 없습니다.",
        )
    return expense
