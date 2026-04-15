from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.enums import CategoryType, DocumentType


REQUIRED_DOCS: dict[CategoryType, list[DocumentType]] = {
    CategoryType.outsourcing: [
        DocumentType.quote,
        DocumentType.comparative_quote,
        DocumentType.service_contract,
        DocumentType.work_order,
        DocumentType.transaction_statement,
        DocumentType.inspection_photos,
        DocumentType.vendor_business_registration,
        DocumentType.vendor_bank_copy,
    ],
    CategoryType.labor: [
        DocumentType.cash_expense_resolution,
        DocumentType.in_kind_expense_resolution,
        DocumentType.researcher_status_sheet,
    ],
    CategoryType.test_report: [
        DocumentType.quote,
        DocumentType.expense_resolution,
        DocumentType.transaction_statement,
    ],
    CategoryType.materials: [
        DocumentType.quote,
        DocumentType.comparative_quote,
        DocumentType.expense_resolution,
        DocumentType.inspection_confirmation,
        DocumentType.vendor_business_registration,
        DocumentType.vendor_bank_copy,
    ],
    CategoryType.meeting: [
        DocumentType.receipt,
        DocumentType.meeting_minutes,
    ],
    CategoryType.other: [],
}

AMOUNT_THRESHOLDS: dict[str, dict[str, Any]] = {
    "comparative_quote_required_above": {
        "outsourcing": 1_000_000,
        "materials": 500_000,
    }
}


@dataclass
class RuleViolation:
    code: str
    message: str
    severity: str = "error"
    field: str | None = None


@dataclass
class RulesCheckResult:
    blocking_errors: list[RuleViolation] = field(default_factory=list)
    warnings: list[RuleViolation] = field(default_factory=list)
    passed_checks: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.blocking_errors) == 0


class RulesEngine:
    """
    Evaluates required document rules by category.
    Returns blocking errors, warnings, and passed checks.
    Never silently ignores failures.
    """

    def check_required_documents(
        self,
        category_type: CategoryType,
        uploaded_doc_types: list[DocumentType],
    ) -> RulesCheckResult:
        result = RulesCheckResult()
        required = REQUIRED_DOCS.get(category_type, [])

        if category_type == CategoryType.other:
            result.passed_checks.append("other_category_custom_docs_accepted")
            return result

        uploaded_set = set(uploaded_doc_types)

        for doc_type in required:
            if doc_type in uploaded_set:
                result.passed_checks.append(f"required_doc_present:{doc_type.value}")
            else:
                result.blocking_errors.append(
                    RuleViolation(
                        code="MISSING_REQUIRED_DOCUMENT",
                        message=f"필수 서류 누락: {doc_type.value} ({self._doc_label(doc_type)})",
                        severity="error",
                        field=doc_type.value,
                    )
                )

        return result

    def check_amount_rules(
        self,
        category_type: CategoryType,
        amount: float,
        uploaded_doc_types: list[DocumentType],
    ) -> RulesCheckResult:
        result = RulesCheckResult()

        thresholds = AMOUNT_THRESHOLDS.get("comparative_quote_required_above", {})
        threshold = thresholds.get(category_type.value)

        if threshold and amount >= threshold:
            if DocumentType.comparative_quote not in uploaded_doc_types:
                result.blocking_errors.append(
                    RuleViolation(
                        code="COMPARATIVE_QUOTE_REQUIRED",
                        message=(
                            f"{category_type.value} 항목 {threshold:,}원 이상 시 "
                            "비교견적서(comparative_quote)가 필수입니다."
                        ),
                        severity="error",
                        field="comparative_quote",
                    )
                )
            else:
                result.passed_checks.append("comparative_quote_present_above_threshold")

        return result

    def check_vendor_consistency(
        self,
        doc_vendor_registrations: list[str | None],
    ) -> RulesCheckResult:
        result = RulesCheckResult()
        non_null = [r for r in doc_vendor_registrations if r]
        unique_registrations = set(non_null)

        if len(unique_registrations) > 1:
            result.blocking_errors.append(
                RuleViolation(
                    code="VENDOR_INCONSISTENCY",
                    message=(
                        "서류 간 사업자등록번호가 일치하지 않습니다: "
                        + ", ".join(unique_registrations)
                    ),
                    severity="error",
                    field="vendor_registration_number",
                )
            )
        elif len(unique_registrations) == 1:
            result.passed_checks.append("vendor_registration_consistent")

        return result

    def _doc_label(self, doc_type: DocumentType) -> str:
        labels: dict[DocumentType, str] = {
            DocumentType.quote: "견적서",
            DocumentType.comparative_quote: "비교견적서",
            DocumentType.service_contract: "용역계약서",
            DocumentType.work_order: "발주서",
            DocumentType.transaction_statement: "거래명세서",
            DocumentType.inspection_photos: "검수사진",
            DocumentType.vendor_business_registration: "공급업체 사업자등록증",
            DocumentType.vendor_bank_copy: "공급업체 통장사본",
            DocumentType.cash_expense_resolution: "현금지급결의서",
            DocumentType.in_kind_expense_resolution: "현물지급결의서",
            DocumentType.researcher_status_sheet: "연구원현황표",
            DocumentType.expense_resolution: "지출결의서",
            DocumentType.inspection_confirmation: "검수확인서",
            DocumentType.receipt: "영수증/카드전표",
            DocumentType.meeting_minutes: "회의록",
        }
        return labels.get(doc_type, doc_type.value)
