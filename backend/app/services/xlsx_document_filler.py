from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.exceptions import DocumentGenerationError
from app.core.logging import get_logger

logger = get_logger(__name__)


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
            raise DocumentGenerationError(
                "셀 매핑 정보가 없습니다. vendor_template_pool 분석을 먼저 실행하세요."
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
        """
        skip_keys = {"sheet_name", "_cell_map", "_mapping_status"}

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
                ws[cell_addr] = value
                written.append(f"{cell_key}={cell_addr}")
            except Exception as e:
                logger.warning("xlsx_cell_set_failed", cell=cell_addr, error=str(e))
                skipped.append(f"{cell_key}({cell_addr}): {e}")
