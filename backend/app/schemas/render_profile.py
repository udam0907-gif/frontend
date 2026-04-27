"""
견적서 템플릿 렌더 프로파일 스키마

render_strategy 선택지:
  docxtpl         — 템플릿에 {{variable}} 플레이스홀더가 있을 때
  paragraph_fill  — 문단 인덱스 기반 (순수 텍스트 구조, 표 없음)
  standard_table  — 고정 테이블/행/열 좌표 기반 (구조화된 표 양식)
  marker_table    — 텍스트 마커로 테이블을 찾는 방식 (기본 fallback)
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ParagraphFillConfig(BaseModel):
    paragraph_map: dict[str, int] = Field(
        default_factory=dict,
        description="필드명 → 문단 인덱스(0-based). 예: {\"issue_date\": 7, \"recipient_name\": 12}",
    )
    line_items_para_start: int | None = Field(
        None,
        description="품목 첫 행이 시작되는 문단 인덱스",
    )
    line_items_columns: list[str] = Field(
        default=["item_name", "spec", "unit", "quantity", "unit_price", "amount", "remark"],
        description="품목 열 순서 (para_start 기준 순서대로)",
    )


class TableCellPos(BaseModel):
    row: int
    col: int


class StandardTableConfig(BaseModel):
    header_table_idx: int = Field(0, description="헤더 테이블 인덱스 (0-based)")
    body_table_idx: int = Field(1, description="본문 테이블 인덱스 (0-based)")
    recipient_pos: TableCellPos = Field(
        default_factory=lambda: TableCellPos(row=0, col=1),
        description="수신처(귀하) 셀 위치",
    )
    date_pos: TableCellPos = Field(
        default_factory=lambda: TableCellPos(row=0, col=4),
        description="발행일자 셀 위치",
    )
    sender_manager_pos: TableCellPos = Field(
        default_factory=lambda: TableCellPos(row=1, col=1),
        description="담당자 셀 위치",
    )
    sender_name_pos: TableCellPos = Field(
        default_factory=lambda: TableCellPos(row=2, col=1),
        description="공급자 회사명 셀 위치",
    )
    line_items_start_row: int = Field(3, description="품목 시작 행 인덱스 (0-based)")
    line_items_end_row: int = Field(7, description="품목 끝 행 인덱스 (exclusive)")
    line_items_columns: dict[str, int] = Field(
        default_factory=lambda: {
            "seq": 0,
            "item_name": 1,
            "spec": 3,
            "unit_price": 4,
            "amount": 5,
        },
        description="열 이름 → 열 인덱스 (0-based)",
    )
    subtotal_pos: TableCellPos | None = Field(None, description="소계 셀 위치")
    total_pos: TableCellPos | None = Field(None, description="합계 셀 위치")
    contact_pos: TableCellPos | None = Field(None, description="담당자 연락처 셀 위치")
    company_email_pos: TableCellPos | None = Field(None, description="회사/이메일 셀 위치")


class MarkerTableConfig(BaseModel):
    date_marker: str = Field("작성일자", description="날짜 테이블 찾기용 마커 텍스트")
    amount_marker: str = Field("합계금액", description="금액 테이블 찾기용 마커 텍스트")
    line_items_marker: str = Field("품목", description="품목 테이블 찾기용 마커 텍스트")
    subtotal_row_offset: int = Field(28, description="품목 테이블 내 소계 행 오프셋")
    vat_row_offset: int = Field(29, description="부가세 행 오프셋")
    total_row_offset: int = Field(30, description="합계 행 오프셋")
    total_col: int = Field(5, description="금액 열 인덱스 (0-based)")


class RenderProfile(BaseModel):
    """템플릿 렌더 프로파일. Templates.render_profile 컬럼에 JSON으로 저장."""

    doc_type: str = Field(..., description="문서 타입. 예: quote, comparative_quote")
    render_strategy: Literal["docxtpl", "paragraph_fill", "standard_table", "marker_table"] = Field(
        ...,
        description=(
            "docxtpl: {{variable}} 플레이스홀더 방식 | "
            "paragraph_fill: 문단 인덱스 직접 채움 | "
            "standard_table: 고정 테이블 좌표 채움 | "
            "marker_table: 마커 텍스트로 테이블 탐색"
        ),
    )
    textbox_replacement: bool = Field(
        True,
        description="True이면 XML 레벨에서 텍스트박스도 치환 (귀하/작성일자/공급자블록)",
    )
    paragraph_config: ParagraphFillConfig | None = None
    standard_table_config: StandardTableConfig | None = None
    marker_table_config: MarkerTableConfig | None = None
    cleanup_patterns: list[str] = Field(
        default_factory=list,
        description="렌더링 전 제거할 샘플/정적 문구 목록",
    )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


# ─── 전략별 예시 JSON (UI 힌트용) ─────────────────────────────────────────────

STRATEGY_EXAMPLES: dict[str, dict[str, Any]] = {
    "paragraph_fill": {
        "doc_type": "quote",
        "render_strategy": "paragraph_fill",
        "textbox_replacement": True,
        "paragraph_config": {
            "paragraph_map": {
                "issue_date": 7,
                "recipient_name": 12,
                "supplier_name": 13,
                "supplier_registration": 15,
                "supplier_business_line": 16,
                "supplier_address": 17,
                "supplier_phone_fax": 18,
                "supplier_business_item_email": 19,
                "subtotal": 47,
                "manager_contact": 51,
            },
            "line_items_para_start": 30,
            "line_items_columns": ["item_name", "spec", "unit", "quantity", "unit_price", "amount", "remark"],
        },
    },
    "standard_table": {
        "doc_type": "quote",
        "render_strategy": "standard_table",
        "textbox_replacement": False,
        "standard_table_config": {
            "header_table_idx": 0,
            "body_table_idx": 1,
            "recipient_pos": {"row": 0, "col": 1},
            "date_pos": {"row": 0, "col": 4},
            "sender_manager_pos": {"row": 1, "col": 1},
            "sender_name_pos": {"row": 2, "col": 1},
            "line_items_start_row": 3,
            "line_items_end_row": 7,
            "line_items_columns": {"seq": 0, "item_name": 1, "spec": 3, "unit_price": 4, "amount": 5},
            "subtotal_pos": {"row": 7, "col": 5},
            "total_pos": {"row": 9, "col": 5},
        },
    },
    "marker_table": {
        "doc_type": "quote",
        "render_strategy": "marker_table",
        "textbox_replacement": True,
        "marker_table_config": {
            "date_marker": "작성일자",
            "amount_marker": "합계금액",
            "line_items_marker": "품목",
            "subtotal_row_offset": 28,
            "vat_row_offset": 29,
            "total_row_offset": 30,
            "total_col": 5,
        },
    },
    "docxtpl": {
        "doc_type": "quote",
        "render_strategy": "docxtpl",
        "textbox_replacement": False,
    },
}
