from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.exceptions import DocumentGenerationError, MappingNotFoundError
from app.core.logging import get_logger

logger = get_logger(__name__)


def _parse_date(date_str: str):
    """날짜 문자열(YYYY-MM-DD 등)을 date 객체로 파싱. 실패 시 None 반환."""
    import re
    from datetime import date
    parts = re.split(r"[-./\s]+", date_str.strip())
    parts = [p for p in parts if p.isdigit()]
    if len(parts) >= 3:
        try:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, OverflowError):
            pass
    return None


def _anchor(ws: Any, cell_addr: str) -> str:
    """
    cell_addr이 병합 영역에 속하면 그 영역의 좌상단(앵커) 좌표를 반환.
    아니면 입력된 cell_addr 그대로 반환.

    openpyxl은 병합 영역의 비-앵커 좌표에 값을 쓰면 무시한다.
    이 헬퍼로 cell_map이 어느 좌표를 반환하든 안전하게 쓰기 가능.
    """
    from openpyxl.utils.cell import (
        coordinate_from_string,
        column_index_from_string,
        get_column_letter,
    )

    try:
        col_letter, row = coordinate_from_string(cell_addr)
        col_idx = column_index_from_string(col_letter)
    except Exception:
        return cell_addr

    for merged_range in ws.merged_cells.ranges:
        if (merged_range.min_row <= row <= merged_range.max_row
                and merged_range.min_col <= col_idx <= merged_range.max_col):
            anchor_col = get_column_letter(merged_range.min_col)
            anchor_row = merged_range.min_row
            return f"{anchor_col}{anchor_row}"
    return cell_addr


class XlsxDocumentFiller:
    """
    cell_map 기반으로 XLSX 템플릿에 값을 채워 새 파일을 생성한다.

    cell_map 구조 (플랫):
    {
        "sheet_name": "시트명",
        "item_name": "A16",
        "spec": "C16",
        "quantity": "E15",
        "unit_price": "F15",
        "amount": "G15",
        "recipient_name": "A4",
        "issue_date": "B9",
        "total_amount": "G26",
        "doc_number": "B8",
        ... 기타 필드
    }

    context 키 → cell_map 키 매핑으로 셀에 값을 채운다.
    """

    # context 키 → cell_map 키 매핑 테이블
    # context에서 값을 가져와서 cell_map의 해당 셀 주소에 쓴다
    FIELD_ALIASES: dict[str, list[str]] = {
        # 수신자/귀하
        "recipient_name": ["recipient_name", "recipient", "귀하", "수신처"],
        # 날짜
        "issue_date": ["issue_date", "execution_date", "expense_date", "작성일", "견적일"],
        # 품목명
        "item_name": ["item_name", "product_name", "title"],
        # 규격
        "spec": ["spec", "specification"],
        # 수량
        "quantity": ["quantity", "qty"],
        # 단가
        "unit_price": ["unit_price", "price"],
        # 합계/금액
        "amount": ["amount", "total"],
        # 총합계
        "total_amount": ["total_amount", "amount"],
        # 문서번호
        "doc_number": ["doc_number", "document_number"],
        # 업체명 (공급자)
        "company_name": ["company_name", "supplier_name", "vendor_name"],
        # 사업자번호
        "registration_number": ["registration_number", "vendor_business_number",
                                 "vendor_registration", "business_number"],
        # 담당자/연락처
        "contact": ["contact", "vendor_contact"],
        # 예산항목
        "budget_item": ["budget_item"],
        # 비고
        "remark": ["remark", "note"],
    }

    def __init__(self) -> None:
        self._output_base = Path(settings.storage_documents_path)
        self._output_base.mkdir(parents=True, exist_ok=True)

    def fill(
        self,
        template_path: str,
        field_map: dict[str, Any],
        context: dict[str, Any],
        expense_item_id: str,
    ) -> str:
        """
        템플릿을 복사 후 context 값으로 셀을 채운다.
        반환값: 생성된 파일 경로
        """
        try:
            import openpyxl
        except ImportError:
            raise DocumentGenerationError("openpyxl이 설치되지 않았습니다.")

        cell_map: dict = field_map.get("_cell_map", {})
        if not cell_map:
            raise MappingNotFoundError(
                "셀 매핑(cell_map)이 없습니다. "
                "업체 관리에서 양식 파일을 다시 업로드하여 매핑을 완료하세요."
            )

        # 1. 템플릿 복사 (원본 보존)
        # .xls이면 .xlsx로 변환하여 저장 (openpyxl은 .xls 미지원)
        src_ext = Path(template_path).suffix.lower()
        output_filename = f"{expense_item_id}_{uuid.uuid4().hex[:8]}.xlsx"
        output_path = str(self._output_base / output_filename)

        if src_ext == ".xls":
            import os as _os
            from app.services.xlsx_cell_mapper import XlsxCellMapper
            converted = XlsxCellMapper.convert_xls_to_xlsx(template_path)
            try:
                shutil.copy2(converted, output_path)
            finally:
                try:
                    _os.unlink(converted)
                except Exception:
                    pass
        else:
            shutil.copy2(template_path, output_path)

        # 2. 복사본 열기
        wb = openpyxl.load_workbook(output_path)
        sheet_name = cell_map.get("sheet_name")
        ws = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.active

        # 2.5. 옛 데이터 초기화 — cell_map 등록 셀 전체를 None으로 클리어
        # shutil.copy2가 원본 업체 데이터를 그대로 복사하므로,
        # 쓰기 전에 반드시 대상 셀을 비워야 한다.
        _CLEAR_SKIP = {"sheet_name", "_cell_map", "_mapping_status", "_meta"}
        for _key, _addr in cell_map.items():
            if _key in _CLEAR_SKIP:
                continue
            if not isinstance(_addr, str) or not _addr:
                continue
            try:
                ws[_anchor(ws, _addr)] = None
            except Exception:
                pass

        # _meta.items_table 컬럼 범위 초기화 (최대 30행)
        _items_meta_clear: dict | None = None
        if isinstance(cell_map.get("_meta"), dict):
            _items_meta_clear = cell_map["_meta"].get("items_table")
        if _items_meta_clear:
            _start_row_clear = _items_meta_clear.get("start_row")
            _cols_clear: dict = _items_meta_clear.get("columns", {})
            if _start_row_clear and _cols_clear:
                for _col_letter in _cols_clear.values():
                    for _row_offset in range(30):
                        try:
                            ws[_anchor(ws, f"{_col_letter}{int(_start_row_clear) + _row_offset}")] = None
                        except Exception:
                            pass

        # 3. 플랫 cell_map으로 셀 채움
        written: list[str] = []
        skipped: list[str] = []
        self._fill_flat(ws, cell_map, context, written, skipped)

        # 4. 저장
        wb.save(output_path)
        wb.close()

        logger.info(
            "xlsx_document_filled",
            output=output_path,
            items=len(written),
            written=written,
            skipped=skipped if skipped else None,
        )
        return output_path

    def _fill_flat(
        self,
        ws: Any,
        cell_map: dict,
        context: dict,
        written: list,
        skipped: list,
    ) -> None:
        """
        플랫 cell_map의 모든 키를 순회하며 context에서 값을 찾아 셀에 쓴다.

        매핑 방식:
        1. cell_map 키와 동일한 context 키 직접 매핑
        2. FIELD_ALIASES 역방향 매핑 (context 키 → cell_map 키)
        3. cell_map 키에 대해 FIELD_ALIASES로 context에서 값 탐색

        확장:
        - _meta.items_table 존재 시 line_items 배열을 다중 행으로 입력
        - issue_date_year/month/day 존재 시 날짜를 분리 셀에 입력
        """
        skip_keys = {
            "sheet_name", "_cell_map", "_mapping_status", "_meta",
            "issue_date_year", "issue_date_month", "issue_date_day",
        }

        # ── 다중 행 라인아이템 처리 ──────────────────────────────────────
        items_meta: dict | None = None
        if isinstance(cell_map.get("_meta"), dict):
            items_meta = cell_map["_meta"].get("items_table")
        if items_meta and context.get("line_items"):
            start_row = items_meta.get("start_row")
            columns: dict = items_meta.get("columns", {})
            if start_row and columns:
                for idx, item in enumerate(context["line_items"]):
                    row = int(start_row) + idx
                    for field_key, col_letter in columns.items():
                        val = item.get(field_key)
                        if val is None and field_key == "unit_price":
                            val = item.get("price")
                        if val is None:
                            continue
                        try:
                            from decimal import Decimal
                            if isinstance(val, Decimal):
                                val = int(val) if val == val.to_integral_value() else float(val)
                        except Exception:
                            pass
                        try:
                            ws[_anchor(ws, f"{col_letter}{row}")] = val
                            written.append(f"line_items[{idx}].{field_key}={col_letter}{row}")
                        except Exception as e:
                            skipped.append(f"line_items[{idx}].{field_key}({col_letter}{row}): {e}")
                # items_table 컬럼 키는 단일 셀 루프에서 제외
                for col_key in columns:
                    skip_keys.add(col_key)

        # ── 날짜 분리 셀 처리 ────────────────────────────────────────────
        year_cell = cell_map.get("issue_date_year")
        month_cell = cell_map.get("issue_date_month")
        day_cell = cell_map.get("issue_date_day")
        if year_cell or month_cell or day_cell:
            raw_date = (
                context.get("expense_date")
                or context.get("issue_date")
                or context.get("execution_date")
            )
            date_obj = None
            if raw_date is not None:
                if hasattr(raw_date, "year"):
                    date_obj = raw_date
                else:
                    date_obj = _parse_date(str(raw_date))
            if date_obj is not None:
                if year_cell:
                    try:
                        ws[_anchor(ws, year_cell)] = date_obj.year
                        written.append(f"issue_date_year={year_cell}")
                    except Exception as e:
                        skipped.append(f"issue_date_year({year_cell}): {e}")
                if month_cell:
                    try:
                        ws[_anchor(ws, month_cell)] = date_obj.month
                        written.append(f"issue_date_month={month_cell}")
                    except Exception as e:
                        skipped.append(f"issue_date_month({month_cell}): {e}")
                if day_cell:
                    try:
                        ws[_anchor(ws, day_cell)] = date_obj.day
                        written.append(f"issue_date_day={day_cell}")
                    except Exception as e:
                        skipped.append(f"issue_date_day({day_cell}): {e}")
            # 분리 처리 여부와 무관하게 issue_date 단일 키는 단일 셀 루프에서 제외
            skip_keys.add("issue_date")

        # ── 단일 셀 1:1 매핑 (기존 로직 그대로) ─────────────────────────
        for cell_key, cell_addr in cell_map.items():
            if cell_key in skip_keys:
                continue
            if not isinstance(cell_addr, str) or not cell_addr:
                continue

            # 값 탐색 순서:
            # 1. context에 cell_key와 동일한 키가 있으면 직접 사용
            value = context.get(cell_key)

            # 2. 없으면 FIELD_ALIASES에서 cell_key에 해당하는 context 키들을 탐색
            if value is None and cell_key in self.FIELD_ALIASES:
                for alias in self.FIELD_ALIASES[cell_key]:
                    value = context.get(alias)
                    if value is not None:
                        break

            # 3. 역방향: cell_key가 어떤 alias에 포함된 경우
            #    (ex: cell_map에 "supplier_name"이 있고 FIELD_ALIASES["company_name"]에
            #    "supplier_name"이 있으면 company_name 값 사용)
            if value is None:
                for canonical, aliases in self.FIELD_ALIASES.items():
                    if cell_key in aliases:
                        value = context.get(canonical)
                        if value is None:
                            for a in aliases:
                                value = context.get(a)
                                if value is not None:
                                    break
                        if value is not None:
                            break

            if value is None:
                skipped.append(f"{cell_key}({cell_addr})")
                continue

            # 날짜 처리
            if hasattr(value, "strftime"):
                value = value.strftime("%Y-%m-%d")

            # Decimal → int/float
            try:
                from decimal import Decimal
                if isinstance(value, Decimal):
                    value = int(value) if value == value.to_integral_value() else float(value)
            except Exception:
                pass

            try:
                ws[_anchor(ws, cell_addr)] = value
                written.append(f"{cell_key}={cell_addr}")
            except Exception as e:
                logger.warning("xlsx_cell_set_failed", cell=cell_addr, error=str(e))
                skipped.append(f"{cell_key}({cell_addr}): {e}")
