from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.database import get_db
from app.models.document import ValidationResult
from app.models.expense import ExpenseItem
from app.models.project import Project
from app.schemas.document import ValidationResultRead
from app.services.validation_service import ValidationService

router = APIRouter(tags=["validation"])
logger = get_logger(__name__)
_validation_service = ValidationService()


@router.post("/expenses/{expense_id}", response_model=ValidationResultRead, status_code=status.HTTP_201_CREATED)
async def validate_expense(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ValidationResult:
    # Load expense with documents
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

    # Load project
    project_result = await db.execute(
        select(Project).where(Project.id == expense.project_id)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="연결된 과제를 찾을 수 없습니다.",
        )

    uploaded_docs = [
        {
            "document_type": doc.document_type.value,
            "vendor_registration_number": doc.extracted_data.get("vendor_registration_number"),
            "extracted_amount": doc.extracted_data.get("amount"),
        }
        for doc in expense.documents
    ]

    result_data = _validation_service.validate(
        expense_item_id=str(expense_id),
        category_type=expense.category_type,
        amount=expense.amount,
        expense_date=expense.expense_date,
        vendor_name=expense.vendor_name,
        vendor_registration_number=expense.vendor_registration_number,
        project_period_start=project.period_start,
        project_period_end=project.period_end,
        uploaded_docs=uploaded_docs,
    )

    # Update expense status
    if result_data["is_valid"]:
        expense.status = __import__("app.models.enums", fromlist=["ExpenseStatus"]).ExpenseStatus.validated
    else:
        expense.status = __import__("app.models.enums", fromlist=["ExpenseStatus"]).ExpenseStatus.rejected

    validation = ValidationResult(
        id=uuid.uuid4(),
        expense_item_id=expense_id,
        blocking_errors=result_data["blocking_errors"],
        warnings=result_data["warnings"],
        passed_checks=result_data["passed_checks"],
        is_valid=result_data["is_valid"],
    )
    db.add(validation)
    await db.flush()
    await db.refresh(validation)
    return validation


@router.get("/expenses/{expense_id}/latest", response_model=ValidationResultRead)
async def get_latest_validation(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ValidationResult:
    result = await db.execute(
        select(ValidationResult)
        .where(ValidationResult.expense_item_id == expense_id)
        .order_by(ValidationResult.created_at.desc())
        .limit(1)
    )
    validation = result.scalar_one_or_none()
    if not validation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="검증 결과를 찾을 수 없습니다. 먼저 검증을 실행하세요.",
        )
    return validation
