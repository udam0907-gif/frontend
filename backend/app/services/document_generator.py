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
from app.schemas.docx_schemas import (
    CATEGORY_TO_CHECKBOX,
    DOCX_COMMON_ALIASES,
    DOCX_FIELD_ALIASES,
    DOCX_SCHEMAS,
)
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
        layout_map: dict[str, Any] | None = None,
        document_type: str | None = None,
    ) -> dict[str, Any]:
        """
        파일 형식을 감지하고 적절한 렌더러로 처리한다.

        우선순위:
          XLSX + layout_map 존재 → layout_map 렌더러 (_generate_xlsx_layout)
          XLSX + layout_map 없음 → field_map 렌더러 (_generate_xlsx, 기존)
          DOCX + document_type in DOCX_SCHEMAS → 스키마 렌더러 (_generate_docx_schema, 신규)
          DOCX + 스키마 없음     → field_map 렌더러 (_generate_docx, 기존)
          PDF/이미지              → passthrough_copy

        render_mode 값:
          "excel_rendered"   - 값 입력 완료
          "mapping_needed"   - 셀 매핑 미설정 → 원본 복사
          "passthrough_copy" - PDF/이미지 원본 복사
          "docx_rendered"    - DOCX 렌더링 성공
        """
        if not Path(template_path).exists():
            raise TemplateError(f"템플릿 파일을 찾을 수 없습니다: {template_path}")

        ext = Path(template_path).suffix.lower()

        if ext in _PASSTHROUGH_EXTS:
            output_path = self._copy_passthrough(template_path, expense_item_id, ext)
            return {
                "output_path": output_path,
                "render_mode": "passthrough_copy",
                "generation_trace": self._basic_trace(template_path, template_id, "passthrough_copy"),
            }

        if ext in _XLSX_EXTS:
            if layout_map:
                return self._generate_xlsx_layout(
                    template_path, layout_map, user_values, project_data, expense_item_id, template_id
                )
            return await self._generate_xlsx(
                template_path, field_map, user_values, project_data, expense_item_id, template_id
            )

        # DOCX — 스키마 있으면 스키마 렌더러 우선, 없으면 field_map 렌더러
        if document_type and document_type in DOCX_SCHEMAS:
            return self._generate_docx_schema(
                template_path, document_type, user_values, project_data, expense_item_id, template_id
            )
        return await self._generate_docx(
            template_path, field_map, user_values, project_data, expense_item_id, template_id
        )

    # ─── DOCX 스키마 렌더러 (DOCX_SCHEMAS 기반, 신규) ──────────────────────

    def _generate_docx_schema(
        self,
        template_path: str,
        document_type: str,
        user_values: dict[str, Any],
        project_data: dict[str, Any],
        expense_item_id: str,
        template_id: str,
    ) -> dict[str, Any]:
        """
        DOCX_SCHEMAS[document_type] 기반 렌더러.
        1) context 구성 (별칭 적용)
        2) checkbox 필드 ■/□ 처리
        3) line_items 반복 블록 구성
        4) docxtpl 렌더링
        """
        schema = DOCX_SCHEMAS[document_type]
        ctx = self._build_schema_context(document_type, user_values, project_data, schema)
        output_path = self._render_docx(template_path, ctx, expense_item_id)

        trace = {
            "template_path": template_path,
            "template_id": template_id,
            "document_type": document_type,
            "renderer": "docx_schema",
            "render_mode": "docx_rendered",
            "scalar_keys": list(schema.scalar_fields.keys()),
            "checkbox_keys": list(schema.checkbox_fields.keys()),
            "line_items_count": len(ctx.get("line_items", [])),
        }
        return {"output_path": output_path, "render_mode": "docx_rendered", "generation_trace": trace}

    def _build_schema_context(
        self,
        document_type: str,
        user_values: dict[str, Any],
        project_data: dict[str, Any],
        schema: Any,
    ) -> dict[str, Any]:
        """DOCX 스키마 전용 context 구성."""
        # 1) 기본 병합 (project_data < user_values 순)
        ctx: dict[str, Any] = {**project_data, **user_values}

        # 2) 공통 별칭 적용 (덮어쓰지 않고 setdefault)
        for src, dst in DOCX_COMMON_ALIASES.items():
            if src in ctx and dst not in ctx:
                ctx[dst] = ctx[src]

        # 3) 문서 타입별 별칭 적용
        for src, dst in DOCX_FIELD_ALIASES.get(document_type, {}).items():
            if src in ctx and dst not in ctx:
                ctx[dst] = ctx[src]

        # 3-b) project_period 자동 생성 (period_start/end 있고 project_period 없을 때)
        if "project_period" not in ctx:
            ps = ctx.get("period_start", "")
            pe = ctx.get("period_end", "")
            if ps and pe:
                ctx["project_period"] = f"{ps} ~ {pe}"

        # 4) checkbox 필드 ■/□ 주입
        if schema.checkbox_fields:
            category = str(ctx.get("category_type", ""))
            checked_field = CATEGORY_TO_CHECKBOX.get(category, "")
            for field_key in schema.checkbox_fields:
                ctx[field_key] = "■" if field_key == checked_field else ""

        # 5) line_items 반복 블록 구성
        if schema.line_items:
            ctx["line_items"] = self._build_line_items(ctx, schema.line_items)

        return ctx

    def _build_line_items(self, ctx: dict[str, Any], li_spec: Any) -> list[dict[str, Any]]:
        """
        line_items 배열 구성.
        - ctx["line_items"]에 이미 배열이 있으면 그대로 사용
        - 없으면 ctx의 스칼라 값(item_name, quantity 등)으로 단일 행 구성
        - max_rows 초과 시 잘림 + 경고 로그
        """
        rows: list[dict[str, Any]] = ctx.get("line_items") or []

        if not rows:
            row = {}
            for col_key in li_spec.columns:
                val = ctx.get(col_key)
                if val is not None:
                    row[col_key] = val
            if row:
                rows = [row]

        if len(rows) > li_spec.max_rows:
            logger.warning(
                "docx_line_items_truncated",
                provided=len(rows),
                max_rows=li_spec.max_rows,
            )
            rows = rows[: li_spec.max_rows]

        # docxtpl은 빈 셀도 렌더링하므로 누락 키를 빈 문자열로 채움
        # seq는 스키마 컬럼 여부와 무관하게 항상 주입 (NO. 열용)
        columns = list(li_spec.columns.keys())
        return [
            {"seq": i + 1, **{col: row.get(col, "") for col in columns}}
            for i, row in enumerate(rows)
        ]

    # ─── DOCX 기존 field_map 렌더러 ({{placeholder}} 방식, legacy) ──────────

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

    # ─── XLSX layout_map 렌더러 ────────────────────────────────────────────

    def _generate_xlsx_layout(
        self,
        template_path: str,
        layout_map: dict[str, Any],
        user_values: dict[str, Any],
        project_data: dict[str, Any],
        expense_item_id: str,
        template_id: str,
    ) -> dict[str, Any]:
        """
        layout_map 구조(scalar / checkbox / table)를 우선 사용하는 XLSX 렌더러.
        layout_map 없을 때는 호출되지 않는다.
        """
        try:
            import openpyxl
            import openpyxl.utils as _xl_utils
        except ImportError:
            raise DocumentGenerationError("openpyxl이 설치되지 않았습니다.")

        try:
            wb = openpyxl.load_workbook(template_path)
        except Exception as e:
            raise DocumentGenerationError(f"XLSX 파일 열기 실패: {e}") from e

        ws = wb.active
        ctx: dict[str, Any] = {**project_data, **user_values}

        # 병합셀 master 주소 반환 헬퍼
        def _master(addr: str) -> str:
            for mr in ws.merged_cells.ranges:
                for r in range(mr.min_row, mr.max_row + 1):
                    for c in range(mr.min_col, mr.max_col + 1):
                        if f"{_xl_utils.get_column_letter(c)}{r}" == addr:
                            return f"{_xl_utils.get_column_letter(mr.min_col)}{mr.min_row}"
            return addr

        # master → 첫 번째 쓰기 필드 추적 (충돌 방지)
        master_claimed: dict[str, str] = {}
        written: list[str] = []
        skipped: list[str] = []

        def _write(field_key: str, cell_addr: str, value: Any) -> None:
            master = _master(cell_addr)
            if master in master_claimed:
                logger.warning(
                    "layout_xlsx_merge_conflict",
                    field=field_key,
                    cell=cell_addr,
                    master=master,
                    owner=master_claimed[master],
                )
                skipped.append(f"{field_key}(병합충돌→{master_claimed[master]})")
                return
            try:
                ws[master] = value
                master_claimed[master] = field_key
                written.append(f"{field_key}→{master}")
            except Exception as e:
                logger.warning("layout_xlsx_write_failed", field=field_key, cell=master, error=str(e))
                skipped.append(f"{field_key}(쓰기실패:{e})")

        # ── 1. scalar_fields ──────────────────────────────────────────────
        for key, meta in layout_map.get("scalar_fields", {}).items():
            cell = meta.get("cell") if isinstance(meta, dict) else getattr(meta, "cell", None)
            if not cell:
                continue
            value = ctx.get(key)
            if value is None:
                skipped.append(f"{key}(값없음)")
                continue
            _write(key, cell, value)

        # ── 2. checkbox_fields ────────────────────────────────────────────
        for key, meta in layout_map.get("checkbox_fields", {}).items():
            if isinstance(meta, dict):
                cell             = meta.get("cell")
                value_map        = meta.get("value_map", {})
                full_string_mode = meta.get("full_string_mode", True)
                template_string  = meta.get("template_string")
            else:
                cell             = getattr(meta, "cell", None)
                value_map        = getattr(meta, "value_map", {})
                full_string_mode = getattr(meta, "full_string_mode", True)
                template_string  = getattr(meta, "template_string", None)

            if not cell:
                continue

            raw_value = ctx.get(key)
            if raw_value is None:
                skipped.append(f"{key}(값없음)")
                continue

            # context 값 → 체크 레이블
            check_label = value_map.get(str(raw_value), str(raw_value))

            if full_string_mode and template_string:
                # □ {label} → ■ {label} 치환
                cell_value = template_string.replace(f"□ {check_label}", f"■ {check_label}")
            else:
                cell_value = check_label

            _write(key, cell, cell_value)

        # ── 3. table_fields ───────────────────────────────────────────────
        for table_key, meta in layout_map.get("table_fields", {}).items():
            if isinstance(meta, dict):
                start_row = meta.get("start_row", 1)
                max_rows  = meta.get("max_rows", 1)
                columns   = meta.get("columns", {})
            else:
                start_row = getattr(meta, "start_row", 1)
                max_rows  = getattr(meta, "max_rows", 1)
                columns   = getattr(meta, "columns", {})

            # line_items 배열 우선, 없으면 ctx 스칼라 값으로 단일 행 구성
            rows: list[dict[str, Any]] = ctx.get(table_key) or []
            if not rows:
                row = {col: ctx.get(col) for col in columns if ctx.get(col) is not None}
                if row:
                    rows = [row]

            if len(rows) > max_rows:
                logger.warning(
                    "layout_xlsx_table_truncated",
                    table=table_key,
                    provided=len(rows),
                    max_rows=max_rows,
                )
                rows = rows[:max_rows]
                skipped.append(f"{table_key}(행잘림:{len(ctx.get(table_key, []))}→{max_rows})")

            for i, row in enumerate(rows):
                for col_key, col_letter in columns.items():
                    value = row.get(col_key)
                    if value is None:
                        continue
                    cell_addr = f"{col_letter}{start_row + i}"
                    _write(f"{table_key}[{i}].{col_key}", cell_addr, value)

        # ── 저장 ─────────────────────────────────────────────────────────
        output_filename = f"{expense_item_id}_{uuid.uuid4().hex[:8]}.xlsx"
        output_path = str(self._output_base / output_filename)
        try:
            wb.save(output_path)
        except Exception as e:
            raise DocumentGenerationError(f"XLSX 저장 실패: {e}") from e

        render_mode = "excel_rendered" if written else "mapping_needed"
        trace = self._basic_trace(template_path, template_id, render_mode)
        trace["renderer"] = "layout_map"
        trace["xlsx_cells_written"] = len(written)
        trace["written_fields"] = written
        if skipped:
            trace["skipped_fields"] = skipped

        return {"output_path": output_path, "render_mode": render_mode, "generation_trace": trace}

    # ─── XLSX 기존 field_map 렌더러 (layout_map 없을 때 유지) ──────────────

    async def _generate_xlsx(
        self,
        template_path: str,
        field_map: dict[str, Any],
        user_values: dict[str, Any],
        project_data: dict[str, Any],
        expense_item_id: str,
        template_id: str,
    ) -> dict[str, Any]:
        try:
            import openpyxl
        except ImportError:
            raise DocumentGenerationError("openpyxl이 설치되지 않았습니다.")

        # cell 주소가 있는 필드가 하나라도 있는지 확인
        cell_mapped_fields = {
            k: v for k, v in field_map.items()
            if isinstance(v, dict) and v.get("cell")
        }

        if not cell_mapped_fields:
            # 셀 매핑 미설정 → 원본 복사 후 mapping_needed 반환
            import shutil as _shutil
            output_filename = f"{expense_item_id}_{uuid.uuid4().hex[:8]}.xlsx"
            output_path = str(self._output_base / output_filename)
            _shutil.copy2(template_path, output_path)
            trace = self._basic_trace(template_path, template_id, "mapping_needed")
            trace["xlsx_cells_written"] = 0
            return {"output_path": output_path, "render_mode": "mapping_needed", "generation_trace": trace}

        # 컨텍스트 구성: user_values 우선, 없으면 project_data
        context: dict[str, Any] = {**project_data, **user_values}

        try:
            wb = openpyxl.load_workbook(template_path)
        except Exception as e:
            raise DocumentGenerationError(f"XLSX 파일 열기 실패: {e}") from e

        ws = wb.active
        written_count = 0
        written_fields: list[str] = []
        skipped_fields: list[str] = []

        # 병합셀 master 주소 캐시 빌드
        import openpyxl.utils as _xl_utils

        def _master_cell(addr: str) -> str:
            """비master 병합셀이면 좌상단 master 주소를 반환, 아니면 원래 주소."""
            for mr in ws.merged_cells.ranges:
                for r in range(mr.min_row, mr.max_row + 1):
                    for c in range(mr.min_col, mr.max_col + 1):
                        if f"{_xl_utils.get_column_letter(c)}{r}" == addr:
                            master = f"{_xl_utils.get_column_letter(mr.min_col)}{mr.min_row}"
                            return master
            return addr

        # master 셀 → 첫 번째 쓰기 필드만 허용 (중복 충돌 방지)
        master_claimed: dict[str, str] = {}

        for field_key, meta in cell_mapped_fields.items():
            cell_address = meta["cell"]
            value = context.get(field_key)
            if value is None:
                skipped_fields.append(f"{field_key}(값없음)")
                continue

            master = _master_cell(cell_address)
            if master != cell_address:
                logger.info(
                    "xlsx_merged_cell_redirect",
                    field=field_key,
                    configured=cell_address,
                    master=master,
                )

            # 같은 master에 이미 다른 필드가 쓰여졌으면 skip
            if master in master_claimed:
                logger.warning(
                    "xlsx_merged_cell_conflict",
                    field=field_key,
                    cell=cell_address,
                    master=master,
                    already_written_by=master_claimed[master],
                )
                skipped_fields.append(f"{field_key}(병합충돌→{master_claimed[master]})")
                continue

            try:
                ws[master] = value
                master_claimed[master] = field_key
                written_count += 1
                written_fields.append(
                    f"{field_key}→{master}" if master != cell_address
                    else f"{field_key}→{cell_address}"
                )
            except Exception as e:
                logger.warning(
                    "xlsx_cell_write_failed",
                    field=field_key,
                    cell=master,
                    error=str(e),
                )
                skipped_fields.append(f"{field_key}(쓰기실패:{e})")

        output_filename = f"{expense_item_id}_{uuid.uuid4().hex[:8]}.xlsx"
        output_path = str(self._output_base / output_filename)
        try:
            wb.save(output_path)
        except Exception as e:
            raise DocumentGenerationError(f"XLSX 저장 실패: {e}") from e

        render_mode = "excel_rendered" if written_count > 0 else "mapping_needed"
        trace = self._basic_trace(template_path, template_id, render_mode)
        trace["xlsx_cells_written"] = written_count
        trace["written_fields"] = written_fields
        if skipped_fields:
            trace["skipped_fields"] = skipped_fields

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
            # source는 _meta 또는 최상위 모두 허용 (이전 호환)
            _meta = meta.get("_meta", {})
            source = _meta.get("source") or meta.get("source", "user_input")
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
