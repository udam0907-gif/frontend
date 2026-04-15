from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.database import get_db
from app.models.document import GeneratedDocument, ValidationResult
from app.models.expense import ExpenseDocument, ExpenseItem
from app.services.export_service import ExportService

router = APIRouter(tags=["export"])
logger = get_logger(__name__)
_export_service = ExportService()


@router.post("/expenses/{expense_id}")
async def export_expense_package(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Load expense
    expense_result = await db.execute(
        select(ExpenseItem)
        .where(ExpenseItem.id == expense_id)
        .options(selectinload(ExpenseItem.documents))
    )
    expense = expense_result.scalar_one_or_none()
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="지출 항목을 찾을 수 없습니다.",
        )

    # Load latest validation
    val_result = await db.execute(
        select(ValidationResult)
        .where(ValidationResult.expense_item_id == expense_id)
        .order_by(ValidationResult.created_at.desc())
        .limit(1)
    )
    validation = val_result.scalar_one_or_none()
    if not validation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="내보내기 전에 검증을 먼저 실행해야 합니다.",
        )

    if not validation.is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "검증 오류가 있는 항목은 내보낼 수 없습니다.",
                "blocking_errors": validation.blocking_errors,
            },
        )

    # Load generated documents
    gen_docs_result = await db.execute(
        select(GeneratedDocument).where(GeneratedDocument.expense_item_id == expense_id)
    )
    gen_docs = gen_docs_result.scalars().all()

    generated_docs_data = [
        {
            "output_path": d.output_path,
            "template_id": str(d.template_id),
            "is_valid": d.is_valid,
            "generation_trace": d.generation_trace,
        }
        for d in gen_docs
    ]

    source_docs_data = [
        {
            "document_type": d.document_type.value,
            "filename": d.filename,
            "file_path": d.file_path,
        }
        for d in expense.documents
    ]

    validation_data = {
        "blocking_errors": validation.blocking_errors,
        "warnings": validation.warnings,
        "passed_checks": validation.passed_checks,
        "is_valid": validation.is_valid,
    }

    zip_path = _export_service.create_export_package(
        expense_item_id=str(expense_id),
        expense_title=expense.title,
        generated_documents=generated_docs_data,
        validation_result=validation_data,
        expense_documents=source_docs_data,
    )

    # Update expense status to exported
    from app.models.enums import ExpenseStatus
    expense.status = ExpenseStatus.exported
    await db.flush()

    logger.info("expense_exported", expense_id=str(expense_id), zip=zip_path)
    return {"message": "내보내기 패키지가 생성되었습니다.", "zip_path": zip_path}


@router.get("/download/{expense_id}")
async def download_export_package(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    from app.config import settings
    exports_path = Path(settings.storage_exports_path)

    # Find latest zip for this expense
    pattern = f"expense_{str(expense_id)[:8]}_*.zip"
    matching = sorted(exports_path.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)

    if not matching:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="내보낸 패키지를 찾을 수 없습니다. 먼저 내보내기를 실행하세요.",
        )

    zip_path = matching[0]
    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=zip_path.name,
    )
