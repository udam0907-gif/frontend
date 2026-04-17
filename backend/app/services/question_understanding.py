from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.services.llm_service import LLMService

logger = get_logger(__name__)

KOREAN_SYNONYMS: dict[str, list[str]] = {
    "한도전용": ["항목 전용", "비목 전용", "예산 전용", "연구비 변경", "연구개발비 변경", "사용계획 변경", "항목 간 변경", "비목 간 조정"],
    "전용": ["항목 이동", "비목 이동", "예산 변경", "항목 변경", "비목 변경"],
    "연구비 총괄 현황표": ["연구비현황표", "총괄현황표", "연구비 현황표", "연구개발비 현황표"],
    "입력": ["등록", "작성", "처리", "기입"],
    "등록": ["입력", "작성", "처리"],
    "집행": ["사용", "지출", "지급", "사용 집행"],
    "승인": ["허가", "허용", "동의", "인가", "결재"],
    "가능": ["허용", "할 수 있", "인정", "허가"],
    "불가": ["금지", "불허", "제한", "할 수 없", "안 됨"],
    "연구비": ["연구개발비", "R&D 비용", "과제비"],
    "실적보고": ["실적 보고", "성과 보고", "연구실적", "과제 실적"],
    "정산": ["결산", "정산 처리", "비용 정산"],
    "변경": ["수정", "조정", "변경 신청", "변경 처리"],
}

CLASSIFICATION_SYSTEM_PROMPT = """당신은 한국 정부 R&D 연구비 관리 질문 분류 전문가입니다.
주어진 질문을 다음 네 가지 유형 중 하나로 정확히 분류하세요:

- rcms_procedure: RCMS(연구비관리시스템)에서 무언가를 어떻게/어디서 하는지 묻는 절차 질문
  예: "RCMS에서 어떻게 입력하나요?", "어디서 등록하나요?", "처리 방법을 알려주세요"

- legal_policy: 무언가가 허용되는지/금지되는지/필요한 승인이 있는지 묻는 법령·규정 질문
  예: "한도전용이 가능한가요?", "외부 연구원 인건비로 집행 가능한가요?", "이 비용이 허용되나요?"

- mixed: 허용 여부(법령)와 RCMS 처리 방법(절차) 둘 다 묻는 복합 질문
  예: "한도전용이 가능하면 RCMS에서 어떻게 처리하나요?", "승인받은 후 등록 방법은?"

- definition: 특정 용어나 문서의 의미/정의를 묻는 질문
  예: "한도전용이 무엇인가요?", "연구비 총괄 현황표란?", "실적보고서가 뭔가요?"

반드시 JSON으로만 응답하세요:
{"question_type": "rcms_procedure|legal_policy|mixed|definition", "reasoning": "분류 이유 한 줄"}"""


@dataclass
class QuestionUnderstandingResult:
    question_type: str
    original_query: str
    normalized_query: str
    expanded_queries: list[str] = field(default_factory=list)
    routing_decision: str = ""


class QuestionUnderstandingService:
    def __init__(self, llm: LLMService) -> None:
        self._llm = llm

    async def understand(self, question: str) -> QuestionUnderstandingResult:
        question_type = await self._classify(question)
        normalized = self._normalize(question)
        expanded = self._expand_queries(normalized, question_type)
        routing = self._decide_routing(question_type)

        result = QuestionUnderstandingResult(
            question_type=question_type,
            original_query=question,
            normalized_query=normalized,
            expanded_queries=expanded,
            routing_decision=routing,
        )
        logger.info(
            "question_understood",
            question_type=question_type,
            expanded_count=len(expanded),
            routing=routing,
        )
        return result

    async def _classify(self, question: str) -> str:
        try:
            response = await self._llm.complete(
                system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
                user_message=f"질문: {question}",
                prompt_version="classification-1.0",
                cache_system=True,
            )
            parsed = self._parse_json(response.content)
            q_type = parsed.get("question_type", "rcms_procedure")
            if q_type not in ("rcms_procedure", "legal_policy", "mixed", "definition"):
                q_type = "rcms_procedure"
            return q_type
        except Exception as e:
            logger.warning("question_classification_failed", error=str(e))
            return self._classify_rule_based(question)

    def _classify_rule_based(self, question: str) -> str:
        q = question.lower()
        legal_keywords = ["가능", "불가", "허용", "금지", "해도 되", "할 수 있", "안 되", "규정", "법령", "기준", "정책"]
        rcms_keywords = ["어떻게", "어디서", "방법", "절차", "입력", "등록", "처리", "RCMS", "rcms", "클릭", "화면"]
        def_keywords = ["이란", "이란?", "란?", "이 뭐", "뭐야", "무엇", "정의", "의미"]

        has_legal = any(k in q for k in legal_keywords)
        has_rcms = any(k in q for k in rcms_keywords)
        has_def = any(k in q for k in def_keywords)

        if has_def:
            return "definition"
        if has_legal and has_rcms:
            return "mixed"
        if has_legal:
            return "legal_policy"
        return "rcms_procedure"

    def _normalize(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text.strip())
        text = re.sub(r"[^\w\s가-힣ㄱ-ㅎㅏ-ㅣ()?,.]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _expand_queries(self, normalized: str, question_type: str) -> list[str]:
        queries: set[str] = {normalized}
        # Add joined/spaced variants
        queries.add(normalized.replace(" ", ""))

        # Synonym expansion
        for term, synonyms in KOREAN_SYNONYMS.items():
            if term in normalized:
                for syn in synonyms:
                    queries.add(normalized.replace(term, syn))

        result = list(queries)[:10]
        return result

    def _decide_routing(self, question_type: str) -> str:
        routing_map = {
            "rcms_procedure": "rcms_only",
            # Always retrieve RCMS too: official FAQ/guides often directly answer policy questions
            "legal_policy": "legal_then_rcms",
            "mixed": "legal_then_rcms",
            "definition": "both_sources",
        }
        return routing_map.get(question_type, "rcms_only")

    def _parse_json(self, content: str) -> dict:
        match = re.search(r"\{.*?\}", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {}
