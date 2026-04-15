from __future__ import annotations

import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from docx import Document as DocxDocument

from app.config import settings
from app.core.exceptions import ParseError, StorageError, TemplateError
from app.core.logging import get_logger
from app.core.security import (
    ALLOWED_TEMPLATE_EXTENSIONS,
    generate_safe_filename,
    validate_file_extension,
)

logger = get_logger(__name__)

PLACEHOLDER_PATTERN = re.compile(r"\{\{([^}]+)\}\}")


class TemplateService:
    """
    Handles template upload, placeholder extraction, and field map building.
    Template structure is NEVER modified — only placeholders are filled.
    """

    def __init__(self) -> None:
        self._base_path = Path(settings.storage_templates_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    def validate_file(self, filename: str, content: bytes) -> None:
        if not validate_file_extension(filename, ALLOWED_TEMPLATE_EXTENSIONS):
            raise TemplateError(
                f"템플릿 파일은 .docx 형식만 허용됩니다. 업로드된 파일: {filename}"
            )
        if len(content) > 20 * 1024 * 1024:
            raise TemplateError("템플릿 파일 크기는 20MB를 초과할 수 없습니다.")

    def save_file(self, original_filename: str, content: bytes) -> tuple[str, str]:
        """Save file and return (safe_filename, file_path)."""
        safe_name = generate_safe_filename(original_filename)
        dest_path = self._base_path / safe_name
        try:
            dest_path.write_bytes(content)
        except OSError as e:
            raise StorageError(f"파일 저장 실패: {e}") from e
        logger.info("template_file_saved", path=str(dest_path), size=len(content))
        return safe_name, str(dest_path)

    def extract_placeholders(self, file_path: str) -> dict[str, Any]:
        """
        Extract all {{placeholder}} patterns from DOCX paragraphs and tables.
        Returns a field_map dict with auto-detected metadata.
        """
        try:
            doc = DocxDocument(file_path)
        except Exception as e:
            raise ParseError(f"DOCX 파일 파싱 실패: {e}") from e

        placeholders: set[str] = set()

        # Scan paragraphs
        for para in doc.paragraphs:
            for match in PLACEHOLDER_PATTERN.finditer(para.text):
                placeholders.add(match.group(1).strip())

        # Scan tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        for match in PLACEHOLDER_PATTERN.finditer(para.text):
                            placeholders.add(match.group(1).strip())

        field_map: dict[str, Any] = {}
        for placeholder in sorted(placeholders):
            field_map[placeholder] = {
                "label": self._auto_label(placeholder),
                "type": self._auto_type(placeholder),
                "required": not placeholder.startswith("optional_"),
                "source": self._auto_source(placeholder),
                "description": None,
            }

        logger.info(
            "placeholders_extracted",
            file=file_path,
            count=len(placeholders),
        )
        return field_map

    def _auto_label(self, placeholder: str) -> str:
        label_map = {
            "project_name": "과제명",
            "project_code": "과제번호",
            "institution": "주관기관",
            "pi_name": "연구책임자",
            "expense_date": "지출일",
            "amount": "금액",
            "vendor_name": "거래처명",
            "vendor_registration": "사업자등록번호",
            "description": "내용 설명",
            "period_start": "협약 시작일",
            "period_end": "협약 종료일",
        }
        return label_map.get(placeholder, placeholder.replace("_", " ").title())

    def _auto_type(self, placeholder: str) -> str:
        if any(k in placeholder for k in ("date", "period", "start", "end")):
            return "date"
        if any(k in placeholder for k in ("amount", "budget", "cost", "price")):
            return "number"
        if "description" in placeholder or "summary" in placeholder or "narrative" in placeholder:
            return "helper_text"
        return "text"

    def _auto_source(self, placeholder: str) -> str:
        project_fields = {
            "project_name", "project_code", "institution",
            "pi_name", "period_start", "period_end",
        }
        if placeholder in project_fields:
            return "project_data"
        if self._auto_type(placeholder) == "helper_text":
            return "llm_generated"
        return "user_input"

    def delete_file(self, file_path: str) -> None:
        try:
            Path(file_path).unlink(missing_ok=True)
        except OSError as e:
            logger.warning("template_file_delete_failed", path=file_path, error=str(e))
