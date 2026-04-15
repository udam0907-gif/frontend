from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Any

from app.core.logging import get_logger
from app.models.enums import CategoryType, DocumentType
from app.schemas.document import ValidationIssue, ValidationResultRead
from app.services.rules_engine import RulesEngine, RulesCheckResult

logger = get_logger(__name__)


class ValidationService:
    """
    Validates expense items against all rules.
    Never silently ignores failures.
    Returns: blocking_errors, warnings, passed_checks.
    """

    def __init__(self) -> None:
        self._rules = RulesEngine()

    def validate(
        self,
        expense_item_id: str,
        category_type: CategoryType,
        amount: Decimal,
        expense_date: str | None,
        vendor_name: str | None,
        vendor_registration_number: str | None,
        project_period_start: date,
        project_period_end: date,
        uploaded_docs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        blocking_errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []
        passed_checks: list[str] = []

        doc_types = [DocumentType(d["document_type"]) for d in uploaded_docs]
        doc_vendor_regs = [d.get("vendor_registration_number") for d in uploaded_docs]

        # Check 1: Required documents
        docs_result = self._rules.check_required_documents(category_type, doc_types)
        blocking_errors.extend(
            ValidationIssue(
                code=v.code, message=v.message, field=v.field, severity=v.severity
            )
            for v in docs_result.blocking_errors
        )
        passed_checks.extend(docs_result.passed_checks)

        # Check 2: Amount rules
        amount_result = self._rules.check_amount_rules(category_type, float(amount), doc_types)
        blocking_errors.extend(
            ValidationIssue(
                code=v.code, message=v.message, field=v.field, severity=v.severity
            )
            for v in amount_result.blocking_errors
        )
        passed_checks.extend(amount_result.passed_checks)

        # Check 3: Project period validity
        if expense_date:
            try:
                exp_date = date.fromisoformat(expense_date)
                if exp_date < project_period_start or exp_date > project_period_end:
                    blocking_errors.append(
                        ValidationIssue(
                            code="EXPENSE_DATE_OUT_OF_PERIOD",
                            message=(
                                f"지출일({expense_date})이 과제 기간 "
                                f"({project_period_start} ~ {project_period_end}) 외입니다."
                            ),
                            field="expense_date",
                            severity="error",
                        )
                    )
                else:
                    passed_checks.append("expense_date_within_project_period")
            except ValueError:
                warnings.append(
                    ValidationIssue(
                        code="INVALID_DATE_FORMAT",
                        message=f"지출일 형식이 올바르지 않습니다: {expense_date}",
                        field="expense_date",
                        severity="warning",
                    )
                )

        # Check 4: Vendor consistency across documents
        vendor_result = self._rules.check_vendor_consistency(doc_vendor_regs)
        blocking_errors.extend(
            ValidationIssue(
                code=v.code, message=v.message, field=v.field, severity=v.severity
            )
            for v in vendor_result.blocking_errors
        )
        warnings.extend(
            ValidationIssue(
                code=v.code, message=v.message, field=v.field, severity=v.severity
            )
            for v in vendor_result.warnings
        )
        passed_checks.extend(vendor_result.passed_checks)

        # Check 5: Amount consistency — warn if amounts differ across docs
        doc_amounts = [
            Decimal(str(d.get("extracted_amount", 0)))
            for d in uploaded_docs
            if d.get("extracted_amount")
        ]
        if doc_amounts:
            if len(set(doc_amounts)) > 1:
                warnings.append(
                    ValidationIssue(
                        code="AMOUNT_INCONSISTENCY",
                        message=(
                            "첨부 서류 간 금액이 일치하지 않습니다. "
                            f"발견된 금액: {[str(a) for a in doc_amounts]}"
                        ),
                        field="amount",
                        severity="warning",
                    )
                )
            else:
                extracted_amount = doc_amounts[0]
                if abs(extracted_amount - amount) > Decimal("1"):
                    warnings.append(
                        ValidationIssue(
                            code="AMOUNT_MISMATCH",
                            message=(
                                f"입력 금액({amount:,}원)과 서류 추출 금액({extracted_amount:,}원)이 "
                                "다릅니다. 확인이 필요합니다."
                            ),
                            field="amount",
                            severity="warning",
                        )
                    )
                else:
                    passed_checks.append("amount_consistent_across_documents")

        is_valid = len(blocking_errors) == 0

        logger.info(
            "validation_completed",
            expense_item_id=expense_item_id,
            is_valid=is_valid,
            blocking_errors=len(blocking_errors),
            warnings=len(warnings),
            passed=len(passed_checks),
        )

        return {
            "blocking_errors": [e.model_dump() for e in blocking_errors],
            "warnings": [w.model_dump() for w in warnings],
            "passed_checks": passed_checks,
            "is_valid": is_valid,
        }
