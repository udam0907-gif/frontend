"""
LayoutMap — 문서 구조 매핑 스키마

field_map (기존): flat dict, cell 주소 중심, 렌더링 엔진이 현재 사용
layout_map (신규): 문서 구조 명세, scalar / checkbox / table 세 범주로 분류

호환 방침:
  - 렌더링 엔진은 계속 field_map 을 읽는다 (변경 없음)
  - layout_map 은 미래 렌더러·UI·검증 엔진을 위한 구조 정의
  - layout_map 이 None 이면 기존 field_map 만 유효
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ─── 필드 타입별 스키마 ──────────────────────────────────────────────────────

class ScalarField(BaseModel):
    """단일 값 → 단일 셀."""
    cell: str = Field(description="셀 주소 (예: B4)")
    label: str | None = None
    required: bool = False
    value_type: str = "text"   # text | number | date


class CheckboxField(BaseModel):
    """하나의 범주형 값 → 체크박스 문자열이 있는 셀."""
    cell: str = Field(description="체크박스 전체 문자열이 있는 셀 주소 (예: B9)")
    label: str | None = None
    # context 값 → 체크 표시할 레이블 (예: {"materials": "연구재료비"})
    value_map: dict[str, str] = Field(default_factory=dict)
    # True: 전체 □/■ 문자열 쓰기 / False: 매핑된 레이블만 쓰기
    full_string_mode: bool = True
    # 원본 양식의 체크박스 문자열 (참조용, 렌더 시 □ → ■ 치환 기준)
    template_string: str | None = None


class TableField(BaseModel):
    """반복 행 테이블 — 품목 목록 등."""
    start_row: int = Field(description="데이터 시작 행 (헤더 다음 행)")
    max_rows: int = Field(description="최대 입력 가능 행 수")
    columns: dict[str, str] = Field(
        description="필드명 → 열 문자 (예: {'item_name': 'B', 'quantity': 'D'})"
    )


# ─── 최상위 레이아웃 스키마 ──────────────────────────────────────────────────

class LayoutMap(BaseModel):
    """템플릿 문서 구조 명세."""
    document_type: str
    scalar_fields: dict[str, ScalarField] = Field(default_factory=dict)
    checkbox_fields: dict[str, CheckboxField] = Field(default_factory=dict)
    table_fields: dict[str, TableField] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LayoutMap":
        return cls.model_validate(data)


# ─── 문서 타입별 구조 초안 ────────────────────────────────────────────────────
# 실제 템플릿 파일 구조를 근거로 작성. 등록 시 PUT /layout-map 으로 저장한다.

DRAFT_EXPENSE_RESOLUTION = LayoutMap(
    document_type="expense_resolution",
    scalar_fields={
        "project_name":   ScalarField(cell="B4", label="과제명",   required=False, value_type="text"),
        "project_number": ScalarField(cell="B5", label="과제번호", required=False, value_type="text"),
        "project_period": ScalarField(cell="E5", label="연구기간", required=False, value_type="text"),
        "execution_date": ScalarField(cell="B6", label="집행일자", required=True,  value_type="date"),
        "vendor_name":    ScalarField(cell="E6", label="납품업자", required=False, value_type="text"),
        "delivery_date":  ScalarField(cell="B7", label="납품일자", required=False, value_type="date"),
        "usage_purpose":  ScalarField(cell="B10", label="사용목적", required=False, value_type="text"),
        "purchase_purpose": ScalarField(cell="B11", label="구매목적", required=False, value_type="text"),
    },
    checkbox_fields={
        "budget_item": CheckboxField(
            cell="B9",
            label="예산항목",
            value_map={
                "materials":   "연구재료비",
                "labor":       "인건비",
                "outsourcing": "연구활동비",
                "meeting":     "연구활동비",
                "test_report": "연구활동비",
                "other":       "간접비",
            },
            full_string_mode=True,
            template_string="□ 연구재료비   □ 인건비   □ 연구활동비   □ 간접비   □ 연구수당",
        ),
    },
    table_fields={
        "line_items": TableField(
            start_row=15,
            max_rows=5,
            columns={
                "item_name":  "B",
                "spec":       "C",
                "quantity":   "D",
                "unit_price": "E",
                # F열은 수식(자동계산) — 쓰기 대상 아님
                "remark":     "G",
            },
        ),
    },
)

DRAFT_QUOTE = LayoutMap(
    document_type="quote",
    scalar_fields={
        "company_name":        ScalarField(cell="B3", label="업체명",     required=True,  value_type="text"),
        "execution_date":      ScalarField(cell="E3", label="견적일자",   required=True,  value_type="date"),
        "vendor_registration": ScalarField(cell="B4", label="사업자등록번호", required=False, value_type="text"),
        "total_amount":        ScalarField(cell="E4", label="견적총액",   required=False, value_type="number"),
    },
    checkbox_fields={},
    table_fields={
        "line_items": TableField(
            start_row=8,
            max_rows=10,
            columns={
                "item_name":  "A",
                "spec":       "B",
                "quantity":   "C",
                "unit_price": "D",
                "amount":     "E",
                "note":       "F",
            },
        ),
    },
)

DRAFT_TRANSACTION_STATEMENT = LayoutMap(
    document_type="transaction_statement",
    scalar_fields={
        "company_name":   ScalarField(cell="B3", label="업체명",     required=True,  value_type="text"),
        "execution_date": ScalarField(cell="E3", label="거래일자",   required=True,  value_type="date"),
        "total_amount":   ScalarField(cell="E4", label="거래총액",   required=False, value_type="number"),
    },
    checkbox_fields={},
    table_fields={
        "line_items": TableField(
            start_row=8,
            max_rows=10,
            columns={
                "item_name":  "A",
                "spec":       "B",
                "quantity":   "C",
                "unit_price": "D",
                "amount":     "E",
                "note":       "F",
            },
        ),
    },
)

DRAFT_INSPECTION_CONFIRMATION = LayoutMap(
    document_type="inspection_confirmation",
    scalar_fields={
        "company_name":   ScalarField(cell="B3", label="업체명",   required=True,  value_type="text"),
        "execution_date": ScalarField(cell="E3", label="검수일자", required=True,  value_type="date"),
        "budget_item":    ScalarField(cell="B5", label="예산항목", required=False, value_type="text"),
        "note":           ScalarField(cell="E5", label="비고",     required=False, value_type="text"),
    },
    checkbox_fields={},
    table_fields={
        "line_items": TableField(
            start_row=9,
            max_rows=5,
            columns={
                "item_name":  "A",
                "spec":       "B",
                "quantity":   "C",
                "unit_price": "D",
                "amount":     "E",
            },
        ),
    },
)

# 초안 레지스트리 (document_type.value → LayoutMap)
LAYOUT_DRAFTS: dict[str, LayoutMap] = {
    "expense_resolution":     DRAFT_EXPENSE_RESOLUTION,
    "quote":                  DRAFT_QUOTE,
    "transaction_statement":  DRAFT_TRANSACTION_STATEMENT,
    "inspection_confirmation": DRAFT_INSPECTION_CONFIRMATION,
}
