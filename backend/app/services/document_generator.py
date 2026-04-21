"""
Document Generator — 파일 형식별 렌더러

렌더링 분기:
  .docx  → docxtpl ({{placeholder}} 채우기)
  .xlsx  → openpyxl (셀 {{placeholder}} 채우기)
  .pdf   → 원본 복사 (passthrough_copy)
  .jpg/.jpeg/.png → 원본 복사 (passthrough_copy)

원칙: LLM은 helper_text 필드에만 사용. 양식 구조 절대 변경 금지.
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

import yaml
from docxtpl import DocxTemplate

from app.config import settings
from app.core.exceptions import (
    DocumentGenerationError,
    TemplateError,
    TemplateStructureViolationError,
)
from app.core.logging import get_logger
from app.services.llm_service import LLMService

logger = get_logger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

_DOCX_EXTS = {".docx"}
_XLSX_EXTS = {".xlsx", ".xls"}
_PASSTHROUGH_EXTS = {".pdf", ".jpg", ".jpeg", ".png"}


class DocumentGenerator:
    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service
        self._output_base = Path(settings.storage_documents_path)
        self._output_base.mkdir(parents=True, exist_ok=True)
        self._prompt_config = self._load_prompt_config()

    def _load_prompt_config(self) -> dict[str, Any]:
        config_path = PROMPTS_DIR / "document_helper.yaml"
        try:
            with open(config_path, encoding="utf-8") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning("document_helper_prompt_not_found", path=str(config_path))
            return {"system": "You are a helpful assistant.", "version": "0.0.0"}

    async def generate(
        self,
        template_path: str,
        field_map: dict[str, Any],
        user_values: dict[str, Any],
        project_data: dict[str, Any],
        expense_item_id: str,
        template_id: str,
    ) -> dict[str, Any]:
        """
        파일 형식을 감지하고 적절한 렌더러로 처리한다.
        반환값에 render_mode 포함:
          "docx_rendered"       - DOCX 렌더링 성공
          "xlsx_rendered"       - XLSX 셀 매핑 성공 (일부)
          "excel_mapping_needed"- XLSX이지만 placeholder 패턴 없음 → 원본 복사
          "passthrough_copy"    - PDF/이미지 원본 복사
        """
        if not Path(template_path).exists():
            raise TemplateError(f"템플릿 파일을 찾을 수 없습니다: {template_path}")

        ext = Path(template_path).suffix.lower()

        # Passthrough: PDF / 이미지
        if ext in _PASSTHROUGH_EXTS:
            output_path = self._copy_passthrough(template_path, expense_item_id, ext)
            return {
                "output_path": output_path,
                "render_mode": "passthrough_copy",
                "generation_trace": self._basic_trace(template_path, template_id, "passthrough_copy"),
            }

        # XLSX
        if ext in _XLSX_EXTS:
            return await self._generate_xlsx(
                template_path, field_map, user_values, project_data, expense_item_id, template_id
            )

        # DOCX (default)
        return await self._generate_docx(
            template_path, field_map, user_values, project_data, expense_item_id, template_id
        )

    # ─── DOCX 렌더러 ────────────────────────────────────────────────────────

    async def _generate_docx(
        self,
        template_path: str,
        field_map: dict[str, Any],
        user_values: dict[str, Any],
        project_data: dict[str, Any],
        expense_item_id: str,
        template_id: str,
    ) -> dict[str, Any]:
        context, llm_fields, token_usage = await self._resolve_fields(
            field_map, user_values, project_data
        )

        output_path = self._render_docx(template_path, context, expense_item_id)

        trace = {
            "template_path": template_path,
            "template_id": template_id,
            "model_version": self._llm._model,
            "prompt_version": self._prompt_config.get("version", "unknown"),
            "render_mode": "docx_rendered",
            "fields_filled": {k: ("***" if "amount" in k else str(v)) for k, v in context.items()},
            "llm_fields": llm_fields,
            "token_usage": token_usage,
            "validation_passed": True,
        }

        return {"output_path": output_path, "render_mode": "docx_rendered", "generation_trace": trace}

    def _render_docx(self, template_path: str, context: dict[str, Any], expense_item_id: str) -> str:
        try:
            tpl = DocxTemplate(template_path)
            safe_context = self._sanitize_context(context)
            tpl.render(safe_context)
            output_filename = f"{expense_item_id}_{uuid.uuid4().hex[:8]}.docx"
            output_path = str(self._output_base / output_filename)
            tpl.save(output_path)
            return output_path
        except Exception as e:
            raise DocumentGenerationError(f"DOCX 렌더링 실패: {e}") from e

    # ─── XLSX 렌더러 ────────────────────────────────────────────────────────

    async def _generate_xlsx(
        self,
        template_path: str,
        field_map: dict[str, Any],
        user_values: dict[str, Any],
        project_data: dict[str, Any],
        expense_item_id: str,
        template_id: str,
    ) -> dict[str, Any]:
        import re
        try:
            import openpyxl
        except ImportError:
            raise DocumentGenerationError("openpyxl이 설치되지 않았습니다.")

        # field_map이 있으면 값 해석, 없으면 컨텍스트로 직접 매핑
        if field_map:
            context, _, _ = await self._resolve_fields(field_map, user_values, project_data)
        else:
            context = {**project_data, **user_values}

        try:
            wb = openpyxl.load_workbook(template_path)
        except Exception as e:
            raise DocumentGenerationError(f"XLSX 파일 열기 실패: {e}") from e

        placeholder_re = re.compile(r"\{\{([^}]+)\}\}")
        replaced_count = 0

        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    if cell.value and isinstance(cell.value, str):
                        def replacer(m: re.Match) -> str:
                            key = m.group(1).strip()
                            val = context.get(key, m.group(0))  # 없으면 원본 유지
                            return str(val)
                        new_val = placeholder_re.sub(replacer, cell.value)
                        if new_val != cell.value:
                            cell.value = new_val
                            replaced_count += 1

        output_filename = f"{expense_item_id}_{uuid.uuid4().hex[:8]}.xlsx"
        output_path = str(self._output_base / output_filename)
        try:
            wb.save(output_path)
        except Exception as e:
            raise DocumentGenerationError(f"XLSX 저장 실패: {e}") from e

        render_mode = "xlsx_rendered" if replaced_count > 0 else "excel_mapping_needed"
        trace = self._basic_trace(template_path, template_id, render_mode)
        trace["xlsx_cells_replaced"] = replaced_count

        return {"output_path": output_path, "render_mode": render_mode, "generation_trace": trace}

    # ─── Passthrough (PDF / 이미지) ──────────────────────────────────────────

    def _copy_passthrough(self, template_path: str, expense_item_id: str, ext: str) -> str:
        output_filename = f"{expense_item_id}_{uuid.uuid4().hex[:8]}{ext}"
        output_path = str(self._output_base / output_filename)
        shutil.copy2(template_path, output_path)
        return output_path

    # ─── 필드 해석 (DOCX/XLSX 공통) ────────────────────────────────────────

    async def _resolve_fields(
        self,
        field_map: dict[str, Any],
        user_values: dict[str, Any],
        project_data: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str], dict[str, int]]:
        """field_map에 따라 우선순위 기준으로 값을 결정한다."""
        context: dict[str, Any] = {}
        llm_fields: list[str] = []
        token_usage: dict[str, int] = {}

        for placeholder, meta in field_map.items():
            source = meta.get("source", "user_input")
            field_type = meta.get("type", "text")

            if placeholder in user_values and user_values[placeholder] is not None:
                context[placeholder] = user_values[placeholder]
                continue

            if source == "project_data" and placeholder in project_data:
                context[placeholder] = project_data[placeholder]
                continue

            if field_type == "helper_text":
                llm_result = await self._fill_helper_text(
                    placeholder=placeholder,
                    label=meta.get("label", placeholder),
                    project_data=project_data,
                    user_values=user_values,
                )
                context[placeholder] = llm_result["text"]
                llm_fields.append(placeholder)
                for k, v in llm_result.get("token_usage", {}).items():
                    token_usage[k] = token_usage.get(k, 0) + v
                continue

            if meta.get("required", True):
                raise DocumentGenerationError(
                    f"필수 항목 누락: {placeholder} ({meta.get('label', placeholder)})"
                )
            context[placeholder] = ""

        # 사용자 값 중 field_map에 없는 키도 컨텍스트에 추가 (업체 원본 양식 지원)
        for k, v in user_values.items():
            if k not in context and v is not None:
                context[k] = v

        return context, llm_fields, token_usage

    # ─── 유틸 ────────────────────────────────────────────────────────────────

    def _sanitize_context(self, context: dict[str, Any]) -> dict[str, Any]:
        import re
        jinja_pattern = re.compile(r"\{[%#].*?[%#]\}", re.DOTALL)
        sanitized = {}
        for k, v in context.items():
            if isinstance(v, str):
                cleaned = jinja_pattern.sub("", v)
                if cleaned != v:
                    raise TemplateStructureViolationError(
                        f"LLM이 템플릿 구조 변경을 시도했습니다. 필드: {k}"
                    )
                sanitized[k] = cleaned
            else:
                sanitized[k] = v
        return sanitized

    def _basic_trace(self, template_path: str, template_id: str, render_mode: str) -> dict:
        return {
            "template_path": template_path,
            "template_id": template_id,
            "render_mode": render_mode,
            "model_version": self._llm._model,
            "prompt_version": self._prompt_config.get("version", "unknown"),
        }

    async def _fill_helper_text(
        self,
        placeholder: str,
        label: str,
        project_data: dict[str, Any],
        user_values: dict[str, Any],
    ) -> dict[str, Any]:
        system = self._prompt_config.get("system", "당신은 R&D 행정 전문가 도우미입니다.")
        prompt_version = self._prompt_config.get("version", "unknown")

        user_msg = (
            f"다음 R&D 과제 서류의 '{label}' 항목을 작성해주세요.\n"
            f"항목 키: {placeholder}\n"
            f"프로젝트 정보: {json.dumps(project_data, ensure_ascii=False)}\n"
            f"사용자 입력 데이터: {json.dumps(user_values, ensure_ascii=False)}\n\n"
            "응답은 해당 항목에 들어갈 텍스트만 반환하세요. "
            "서식이나 마크다운 없이 순수 텍스트로만 작성하세요. "
            "절대로 템플릿 구조({%...%}, {#...#})를 포함하지 마세요."
        )

        response = await self._llm.complete(
            system_prompt=system,
            user_message=user_msg,
            prompt_version=prompt_version,
        )

        return {"text": response.content.strip(), "token_usage": response.token_usage}
