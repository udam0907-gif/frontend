"""
DOCX 문서 타입별 변수 스키마 정의

설계 원칙:
  - 회사별 DOCX 양식이 달라도 동일한 {{variable}} 이름을 사용한다
  - 특정 파일/회사 하드코딩 없음. document_type만 선언하면 같은 구조 적용
  - 향후 새 양식 업로드 시 이 스키마가 렌더링 계약이 된다
  - 렌더러는 docxtpl 기준: {{scalar}}, {% for item in line_items %} 블록

파일 형식별 역할:
  DOCX → 자동 출력 주력 (docxtpl {{variable}} 채우기)
  XLSX → legacy/이행용 (기존 field_map 셀 매핑 유지)
  PDF/JPG/PNG → 첨부용 (passthrough_copy)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ─── 필드 메타 기술자 ────────────────────────────────────────────────────────

@dataclass
class FieldSpec:
    """단일 변수 명세."""
    label: str                     # 한국어 UI 레이블
    value_type: str = "text"       # text | number | date | checkbox
    required: bool = False
    description: str = ""


@dataclass
class LineItemColumnSpec:
    """line_items 반복 블록의 열 명세."""
    label: str
    value_type: str = "text"       # text | number
    required: bool = False


@dataclass
class LineItemsSpec:
    """반복 품목 테이블 명세."""
    max_rows: int
    columns: dict[str, LineItemColumnSpec]


@dataclass
class DocxSchema:
    """
    문서 타입별 DOCX 변수 스키마.
    scalar_fields : 단일 값 변수 (헤더·날짜·금액 등)
    checkbox_fields: 범주형 선택 변수 (세목 체크 등)
    line_items     : 반복 품목 블록 (없으면 None)
    """
    document_type: str
    scalar_fields: dict[str, FieldSpec]
    checkbox_fields: dict[str, FieldSpec] = field(default_factory=dict)
    line_items: LineItemsSpec | None = None

    def all_variable_names(self) -> list[str]:
        """DOCX 템플릿에 사용해야 하는 전체 변수명 목록."""
        names = list(self.scalar_fields) + list(self.checkbox_fields)
        if self.line_items:
            names += [f"line_items.{col}" for col in self.line_items.columns]
        return names


# ─── 공통 line_items 컬럼 세트 ──────────────────────────────────────────────

_QUOTE_COLUMNS = {
    "item_name":  LineItemColumnSpec("품명",   "text",   True),
    "spec":       LineItemColumnSpec("규격",   "text",   False),
    "quantity":   LineItemColumnSpec("수량",   "number", True),
    "unit_price": LineItemColumnSpec("단가",   "number", True),
    "amount":     LineItemColumnSpec("금액",   "number", False),   # 자동계산 가능
    "remark":     LineItemColumnSpec("비고",   "text",   False),
}

_INSPECTION_COLUMNS = {
    "item_name":  LineItemColumnSpec("품명",   "text",   True),
    "spec":       LineItemColumnSpec("규격",   "text",   False),
    "quantity":   LineItemColumnSpec("수량",   "number", True),
    "result":     LineItemColumnSpec("검수결과", "text",  False),
    "remark":     LineItemColumnSpec("비고",   "text",   False),
}


# ─── 체크박스 공통 세목 필드 (지출결의서 전용) ──────────────────────────────
# DOCX 템플릿 변수: {{budget_item_research_materials}} 등
# 렌더러가 category_type과 매핑하여 "■" 또는 "" 주입

BUDGET_ITEM_CHECKBOX_FIELDS: dict[str, FieldSpec] = {
    "budget_item_research_materials": FieldSpec("연구재료비", "checkbox", False,
        "category_type=materials → '■', 나머지 → ''"),
    "budget_item_labor":              FieldSpec("인건비",     "checkbox", False,
        "category_type=labor → '■', 나머지 → ''"),
    "budget_item_activity":           FieldSpec("연구활동비", "checkbox", False,
        "category_type=outsourcing|meeting|test_report → '■', 나머지 → ''"),
    "budget_item_indirect":           FieldSpec("간접비",     "checkbox", False,
        "category_type=other → '■', 나머지 → ''"),
    "budget_item_allowance":          FieldSpec("연구수당",   "checkbox", False,
        "별도 category_type 추가 시 사용"),
}

# category_type.value → 체크할 checkbox 필드명
CATEGORY_TO_CHECKBOX: dict[str, str] = {
    "materials":   "budget_item_research_materials",
    "labor":       "budget_item_labor",
    "outsourcing": "budget_item_activity",
    "meeting":     "budget_item_activity",
    "test_report": "budget_item_activity",
    "other":       "budget_item_indirect",
}


# ─── 문서 타입별 스키마 정의 ──────────────────────────────────────────────────

SCHEMA_QUOTE = DocxSchema(
    document_type="quote",
    scalar_fields={
        # 발행자 측 (공급자 = 업체)
        "supplier_name":                FieldSpec("업체명(공급자)",    "text",   True),
        "supplier_registration_number": FieldSpec("사업자등록번호",    "text",   False),
        "supplier_address":             FieldSpec("업체 주소",         "text",   False),
        "supplier_contact":             FieldSpec("업체 연락처",       "text",   False),
        # 수신자 측 (발주처 = 과제 수행기관)
        "recipient_name":               FieldSpec("수신처(발주처명)", "text",   False),
        # 문서 메타
        "issue_date":                   FieldSpec("견적일자",          "date",   True),
        "document_number":              FieldSpec("문서번호",          "text",   False),
        "valid_until":                  FieldSpec("견적 유효기간",     "text",   False),
        # 금액 집계
        "budget_item":                  FieldSpec("예산항목",          "text",   False),
        "subtotal":                     FieldSpec("공급가액(소계)",    "number", False),
        "vat":                          FieldSpec("부가세",            "number", False),
        "total_amount":                 FieldSpec("합계금액",          "number", True),
        "total_amount_korean":          FieldSpec("합계금액(한글)",    "text",   False),
        "remark":                       FieldSpec("비고",              "text",   False),
    },
    line_items=LineItemsSpec(max_rows=10, columns=_QUOTE_COLUMNS),
)

SCHEMA_COMPARATIVE_QUOTE = DocxSchema(
    document_type="comparative_quote",
    scalar_fields={
        **SCHEMA_QUOTE.scalar_fields,
        # 비교견적 추가 메타
        "comparative_note": FieldSpec("비교견적 사유", "text", False),
    },
    line_items=LineItemsSpec(max_rows=10, columns=_QUOTE_COLUMNS),
)

SCHEMA_TRANSACTION_STATEMENT = DocxSchema(
    document_type="transaction_statement",
    scalar_fields={
        "supplier_name":                FieldSpec("업체명(공급자)",    "text",   True),
        "supplier_registration_number": FieldSpec("사업자등록번호",    "text",   False),
        "recipient_name":               FieldSpec("수신처",            "text",   False),
        "issue_date":                   FieldSpec("거래일자",          "date",   True),
        "document_number":              FieldSpec("문서번호",          "text",   False),
        "subtotal":                     FieldSpec("공급가액",          "number", False),
        "vat":                          FieldSpec("부가세",            "number", False),
        "total_amount":                 FieldSpec("합계금액",          "number", True),
        "total_amount_korean":          FieldSpec("합계금액(한글)",    "text",   False),
        "remark":                       FieldSpec("비고",              "text",   False),
    },
    line_items=LineItemsSpec(max_rows=10, columns=_QUOTE_COLUMNS),
)

SCHEMA_INSPECTION_CONFIRMATION = DocxSchema(
    document_type="inspection_confirmation",
    scalar_fields={
        "contract_name":    FieldSpec("계약명(구매명)",     "text",   True),
        "buyer_name":       FieldSpec("발주기업(대표자)",   "text",   False),
        "vendor_name":      FieldSpec("공급처(계약상대자)", "text",   True),
        "purchase_amount":  FieldSpec("구매금액(VAT포함)",  "number", True),
        "contract_period":  FieldSpec("계약기간(납품기간)", "text",   False),
        "delivery_date":    FieldSpec("납품일자",           "date",   False),
        "inspection_date":  FieldSpec("검수일자",           "date",   True),
        "inspection_result":FieldSpec("검수 결과 요약",     "text",   False),
        "inspector_name":   FieldSpec("검수자명",           "text",   False),
        "remark":           FieldSpec("비고",               "text",   False),
    },
    line_items=LineItemsSpec(max_rows=10, columns=_INSPECTION_COLUMNS),
)

SCHEMA_EXPENSE_RESOLUTION = DocxSchema(
    document_type="expense_resolution",
    scalar_fields={
        "project_name":     FieldSpec("과제명",     "text",   True),
        "project_number":   FieldSpec("과제번호",   "text",   False),
        "project_period":   FieldSpec("연구기간",   "text",   False),
        "execution_date":   FieldSpec("발의(집행)일자", "date", True),
        "vendor_name":      FieldSpec("납품업자",   "text",   True),
        "delivery_date":    FieldSpec("납품일자",   "date",   False),
        "usage_purpose":    FieldSpec("사용목적",   "text",   False),
        "purchase_purpose": FieldSpec("구매목적",   "text",   False),
        "total_amount":     FieldSpec("합계금액",   "number", True),
        "remark":           FieldSpec("비고",       "text",   False),
    },
    checkbox_fields=BUDGET_ITEM_CHECKBOX_FIELDS,
    line_items=LineItemsSpec(
        max_rows=5,
        columns={
            "item_name":  LineItemColumnSpec("품명",   "text",   True),
            "spec":       LineItemColumnSpec("규격",   "text",   False),
            "quantity":   LineItemColumnSpec("수량",   "number", True),
            "unit_price": LineItemColumnSpec("단가",   "number", True),
            "amount":     LineItemColumnSpec("금액",   "number", False),
            "remark":     LineItemColumnSpec("비고",   "text",   False),
        },
    ),
)


# ─── 스키마 레지스트리 ────────────────────────────────────────────────────────

DOCX_SCHEMAS: dict[str, DocxSchema] = {
    "quote":                   SCHEMA_QUOTE,
    "comparative_quote":       SCHEMA_COMPARATIVE_QUOTE,
    "transaction_statement":   SCHEMA_TRANSACTION_STATEMENT,
    "inspection_confirmation": SCHEMA_INSPECTION_CONFIRMATION,
    "expense_resolution":      SCHEMA_EXPENSE_RESOLUTION,
}


# ─── 문서 타입별 context 별칭 매핑 ──────────────────────────────────────────
# _build_context()가 만든 flat context 키 → DOCX 변수명
# 문서 타입마다 같은 소스 키가 다른 이름으로 쓰임

DOCX_FIELD_ALIASES: dict[str, dict[str, str]] = {
    "quote": {
        "vendor_name":                 "supplier_name",
        "vendor_registration":         "supplier_registration_number",
        "expense_date":                "issue_date",
        "institution":                 "recipient_name",
    },
    "comparative_quote": {
        "vendor_name":                 "supplier_name",
        "vendor_registration":         "supplier_registration_number",
        "expense_date":                "issue_date",
        "institution":                 "recipient_name",
    },
    "transaction_statement": {
        "vendor_name":                 "supplier_name",
        "vendor_registration":         "supplier_registration_number",
        "expense_date":                "issue_date",
    },
    "inspection_confirmation": {
        "expense_date":                "inspection_date",
        "title":                       "contract_name",
        "institution":                 "buyer_name",
    },
    "expense_resolution": {
        "expense_date":                "execution_date",
    },
}

# 모든 문서 타입에 공통 적용되는 별칭
DOCX_COMMON_ALIASES: dict[str, str] = {
    "project_name":    "project_name",
    "project_code":    "project_number",
    "amount":          "total_amount",
    "product_name":    "item_name",    # 단일 품목용 → line_items 구성 시 사용
}
