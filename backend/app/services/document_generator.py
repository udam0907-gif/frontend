from __future__ import annotations

import json
import os
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


class DocumentGenerator:
    """
    Fills DOCX templates using docxtpl.
    LLM is ONLY used to fill fields tagged as helper_text.
    Template structure is NEVER modified by LLM.
    Validates output against field_map before returning.
    """

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
        Priority order for field resolution:
        1. User-provided values
        2. Project data
        3. LLM-generated helper text (only for helper_text fields)
        """
        if not Path(template_path).exists():
            raise TemplateError(f"템플릿 파일을 찾을 수 없습니다: {template_path}")

        context: dict[str, Any] = {}
        llm_fields_used: list[str] = []
        token_usage_total: dict[str, int] = {}

        for placeholder, meta in field_map.items():
            source = meta.get("source", "user_input")
            field_type = meta.get("type", "text")

            # Priority 1: user input
            if placeholder in user_values and user_values[placeholder] is not None:
                context[placeholder] = user_values[placeholder]
                continue

            # Priority 2: project data
            if source == "project_data" and placeholder in project_data:
                context[placeholder] = project_data[placeholder]
                continue

            # Priority 3: LLM for helper_text only
            if field_type == "helper_text":
                llm_result = await self._fill_helper_text(
                    placeholder=placeholder,
                    label=meta.get("label", placeholder),
                    project_data=project_data,
                    user_values=user_values,
                )
                context[placeholder] = llm_result["text"]
                llm_fields_used.append(placeholder)
                for k, v in llm_result.get("token_usage", {}).items():
                    token_usage_total[k] = token_usage_total.get(k, 0) + v
                continue

            # Required field missing
            if meta.get("required", True):
                raise DocumentGenerationError(
                    f"필수 항목 누락: {placeholder} ({meta.get('label', placeholder)}). "
                    "사용자 입력 또는 프로젝트 데이터에서 값을 찾을 수 없습니다."
                )

            # Optional: empty string
            context[placeholder] = ""

        # Validate context has all required placeholders
        missing_required = [
            p for p, m in field_map.items()
            if m.get("required", True) and context.get(p) in (None, "")
            and m.get("type") != "helper_text"
        ]
        if missing_required:
            raise DocumentGenerationError(
                f"다음 필수 항목이 채워지지 않았습니다: {', '.join(missing_required)}"
            )

        # Fill template — LLM NEVER touches template structure
        output_path = self._render_template(template_path, context, expense_item_id)

        generation_trace = {
            "template_path": template_path,
            "template_id": template_id,
            "model_version": self._llm._model,
            "prompt_version": self._prompt_config.get("version", "unknown"),
            "fields_filled": {k: ("***" if "amount" in k else str(v)) for k, v in context.items()},
            "llm_fields": llm_fields_used,
            "token_usage": token_usage_total,
            "validation_passed": True,
        }

        logger.info(
            "document_generated",
            expense_item_id=expense_item_id,
            output_path=output_path,
            llm_fields_count=len(llm_fields_used),
        )

        return {
            "output_path": output_path,
            "generation_trace": generation_trace,
        }

    def _render_template(
        self, template_path: str, context: dict[str, Any], expense_item_id: str
    ) -> str:
        try:
            tpl = DocxTemplate(template_path)
            # Ensure LLM-provided values don't sneak in structural elements
            safe_context = self._sanitize_context(context)
            tpl.render(safe_context)
            output_filename = f"{expense_item_id}_{uuid.uuid4().hex[:8]}.docx"
            output_path = str(self._output_base / output_filename)
            tpl.save(output_path)
            return output_path
        except Exception as e:
            raise DocumentGenerationError(f"템플릿 렌더링 실패: {e}") from e

    def _sanitize_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """Strip any Jinja2 structural tokens from LLM-generated values."""
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

        return {
            "text": response.content.strip(),
            "token_usage": response.token_usage,
        }
