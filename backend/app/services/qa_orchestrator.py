from __future__ import annotations

import json
import re
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.services.legal_rag_service import LegalRagService
from app.services.llm_service import LLMService
from app.services.question_understanding import QuestionUnderstandingService
from app.services.rag_service import RagService

logger = get_logger(__name__)

EXPERT_SYSTEM_PROMPT = """당신은 한국 정부 R&D 연구비 집행 전문 도우미입니다.
제공된 법령/매뉴얼 발췌문만을 근거로 전문가 수준의 답변을 제공합니다.

근거 자료 우선순위:
  tier_1: 법령 원문 / 시행령 / 행정규칙
  tier_2: 공식 FAQ / 공식 운영안내 / 기관 공식 가이드 / RCMS 공식 FAQ
  tier_3: 일반 교육매뉴얼 / 간접 언급 / 주변 맥락

규칙:
1. tier_2 자료(공식 FAQ/운영안내)에 직접 답변이 있으면 그것을 최우선 근거로 사용합니다
2. tier_1이 없어도 tier_2만으로 결론/조건/절차를 제시할 수 있습니다
3. 제공된 자료 외에는 절대 추측하거나 외부 지식을 사용하지 않습니다
4. 결론을 먼저 명확하게 제시합니다 (허용/불가/조건부/승인필요)
5. 조건·예외사항을 명시합니다
6. RCMS 처리 절차를 단계별로 안내합니다 (관련 경우)
7. 항상 유효한 JSON으로만 응답합니다"""

# Filename patterns that identify authoritative tier_2 documents
# NOTE: "매뉴얼"/"manual" are intentionally excluded — all files are manuals,
#       so those patterns are too broad and would classify everything as tier_2.
_TIER2_FILENAME_PATTERNS = [
    "자주묻는", "faq", "자주_묻는", "운영안내", "업무안내",
    "가이드", "guide", "공지", "안내문", "지침", "처리기준", "운용지침",
]

# Regex patterns indicating a direct operational answer in chunk text
_DIRECT_ANSWER_RE = re.compile(
    r"(가능합니다|가능\s*합니다|가능하다는|가능하며|가능한\s*경우|전용\s*가능|전용이\s*가능"
    r"|가능하지\s*않|불가합니다|불가\s*합니다|불가능합니다|불가합니다|불가\s*합니다"
    r"|허용됩니다|허용\s*됩니다|허용되지\s*않|허용합니다"
    r"|승인\s*필요|승인\s*후\s*가능|사전\s*승인|사전승인"
    r"|처리\s*방법|처리\s*절차|아래와\s*같이|다음과\s*같이|다음\s*조건"
    r"|조건부\s*허용|아래\s*절차|아래\s*기준|답변\s*내용|답변드리"
    r"|①|②|③|④|1\.\s|2\.\s|3\.\s)",
    re.IGNORECASE,
)


class QaOrchestrator:
    def __init__(
        self,
        llm: LLMService,
        rag: RagService,
        legal_rag: LegalRagService,
    ) -> None:
        self._llm = llm
        self._rag = rag
        self._legal_rag = legal_rag
        self._qu = QuestionUnderstandingService(llm)

    async def answer(
        self,
        db: AsyncSession,
        question: str,
        manual_ids: list[uuid.UUID] | None = None,
        debug_mode: bool = False,
    ) -> dict[str, Any]:
        # A: Question Understanding
        understanding = await self._qu.understand(question)

        # B+C: Source Routing + Multi-source Retrieval
        rcms_chunks, legal_chunks = await self._retrieve_by_routing(
            db, understanding, manual_ids
        )

        all_chunks = rcms_chunks + legal_chunks

        if not all_chunks:
            return self._build_not_found_response(understanding, debug_mode)

        max_conf = max(c["similarity"] for c in all_chunks)
        if max_conf < 0.35:
            return self._build_not_found_response(understanding, debug_mode)

        # D: Rule Card Extraction (for legal/policy questions)
        rule_cards: list[dict] = []
        if understanding.question_type in ("legal_policy", "mixed"):
            rule_cards = await self._extract_rule_cards(
                question, legal_chunks, rcms_chunks
            )

        # E: Answerability Assessment
        answerability = self._assess_answerability(
            understanding.question_type, all_chunks, rule_cards
        )

        # F: Structured Answer Generation
        answer = await self._generate_structured_answer(
            question=question,
            understanding=understanding,
            rcms_chunks=rcms_chunks,
            legal_chunks=legal_chunks,
            rule_cards=rule_cards,
            answerability=answerability,
        )

        debug_info: dict | None = None
        if debug_mode:
            debug_info = {
                "question_type": understanding.question_type,
                "normalized_query": understanding.normalized_query,
                "expanded_queries": understanding.expanded_queries,
                "routing_decision": understanding.routing_decision,
                "rcms_candidates": [
                    {
                        "chunk_id": c["chunk_id"],
                        "display_name": c.get("display_name", ""),
                        "page": c.get("page_number"),
                        "section": c.get("section_title", ""),
                        "similarity": round(c["similarity"], 4),
                        "excerpt": c["chunk_text"][:150],
                    }
                    for c in rcms_chunks
                ],
                "legal_candidates": [
                    {
                        "chunk_id": c["chunk_id"],
                        "law_name": c.get("law_name", ""),
                        "article": c.get("article_number", ""),
                        "similarity": round(c["similarity"], 4),
                        "excerpt": c["chunk_text"][:150],
                    }
                    for c in legal_chunks
                ],
                "rule_cards": rule_cards,
                "answerability": answerability,
            }

        return {
            **answer,
            "debug": debug_info,
            "question_understanding": {
                "question_type": understanding.question_type,
                "normalized_query": understanding.normalized_query,
                "expanded_queries": understanding.expanded_queries,
                "routing_decision": understanding.routing_decision,
            },
            "retrieved_chunks": [
                {
                    "chunk_id": c["chunk_id"],
                    "source_type": c.get("source_type", "rcms"),
                    "name": c.get("display_name") or c.get("law_name", ""),
                    "similarity": round(c["similarity"], 4),
                }
                for c in all_chunks[:10]
            ],
        }

    async def _retrieve_by_routing(
        self,
        db: AsyncSession,
        understanding: Any,
        manual_ids: list[uuid.UUID] | None,
    ) -> tuple[list[dict], list[dict]]:
        routing = understanding.routing_decision
        queries = understanding.expanded_queries or [understanding.normalized_query]

        rcms_chunks: list[dict] = []
        legal_chunks: list[dict] = []

        # Embed the primary query once
        try:
            primary_embedding = await self._rag.embed_text(understanding.normalized_query)
        except Exception as e:
            logger.error("embedding_failed", error=str(e))
            return [], []

        if routing in ("rcms_only", "legal_then_rcms", "both_sources"):
            # Vector search
            vec_rcms = await self._rag.search_chunks(
                db, primary_embedding, manual_ids, top_k=6
            )
            # pg_trgm keyword search
            kw_rcms = await self._rag.keyword_search_chunks(
                db, queries[:3], manual_ids, top_k=4
            )
            # ILIKE text match — bypasses OCR noise, gets guaranteed slots
            key_terms = self._extract_key_terms(understanding.normalized_query, queries)
            tm_rcms = await self._rag.text_match_chunks(
                db, key_terms, manual_ids, top_k=4
            ) if key_terms else []
            # Merge vector + trgm first (sorted by similarity)
            high_sim_map: dict[str, dict] = {}
            for c in vec_rcms + kw_rcms:
                cid = c["chunk_id"]
                if cid not in high_sim_map or c["similarity"] > high_sim_map[cid]["similarity"]:
                    high_sim_map[cid] = c
            top_by_sim = sorted(high_sim_map.values(), key=lambda x: -x["similarity"])[:6]
            # Text-match chunks that aren't already in the top-6 get 2 guaranteed slots
            tm_new = [c for c in tm_rcms if c["chunk_id"] not in high_sim_map][:2]
            rcms_chunks = top_by_sim + tm_new
            for c in rcms_chunks:
                c["source_type"] = "rcms"

        if routing in ("legal_first", "legal_then_rcms", "both_sources"):
            # Vector search
            vec_legal = await self._legal_rag.search_chunks(db, primary_embedding, top_k=6)
            # Keyword search
            kw_legal = await self._legal_rag.keyword_search_chunks(db, queries[:3], top_k=4)
            # Merge: deduplicate by chunk_id, keep highest similarity
            legal_map: dict[str, dict] = {}
            for c in vec_legal + kw_legal:
                cid = c["chunk_id"]
                if cid not in legal_map or c["similarity"] > legal_map[cid]["similarity"]:
                    legal_map[cid] = c
            legal_chunks = sorted(legal_map.values(), key=lambda x: -x["similarity"])[:6]

        return rcms_chunks, legal_chunks

    async def _extract_rule_cards(
        self,
        question: str,
        legal_chunks: list[dict],
        rcms_chunks: list[dict],
    ) -> list[dict]:
        if not legal_chunks and not rcms_chunks:
            return []

        context_parts = []
        for i, c in enumerate(legal_chunks[:4]):
            context_parts.append(
                f"[법령 {i+1}] {c.get('law_name', '')} "
                f"{c.get('article_number', '')} {c.get('article_title', '')}\n"
                f"{c['chunk_text']}"
            )
        for i, c in enumerate(rcms_chunks[:2]):
            context_parts.append(
                f"[매뉴얼 {i+1}] {c.get('display_name', '')} "
                f"p.{c.get('page_number', '')}\n"
                f"{c['chunk_text']}"
            )

        prompt = (
            f"다음 법령/매뉴얼 발췌문에서 아래 질문과 관련된 규정을 Rule Card 형식으로 추출하세요.\n\n"
            f"질문: {question}\n\n"
            "발췌문:\n" + "\n\n".join(context_parts) + "\n\n"
            "각 관련 규정마다 아래 JSON 배열 형식으로 추출하세요 (최대 3개):\n"
            "[\n"
            "  {\n"
            '    "topic": "관련 주제",\n'
            '    "source_type": "legal 또는 rcms",\n'
            '    "source_name": "법령명 또는 매뉴얼명",\n'
            '    "section_title": "조문/섹션 제목",\n'
            '    "page_or_article": "조문번호 또는 페이지",\n'
            '    "conclusion_type": "allowed|not_allowed|conditional|approval_required|unclear",\n'
            '    "conclusion_text": "결론 한 줄",\n'
            '    "conditions": ["조건1", "조건2"],\n'
            '    "exceptions": ["예외1"],\n'
            '    "required_documents": ["필요서류1"],\n'
            '    "responsible_authority": "담당기관 또는 null",\n'
            '    "rcms_handling_hint": "RCMS 처리 힌트 또는 null",\n'
            '    "confidence": 0.0~1.0,\n'
            '    "supporting_excerpt": "발췌문 (100자 이내)"\n'
            "  }\n"
            "]\n\n"
            "직접 관련 규정이 없으면 빈 배열 []을 반환하세요."
        )

        try:
            response = await self._llm.complete(
                system_prompt=EXPERT_SYSTEM_PROMPT,
                user_message=prompt,
                prompt_version="rule-card-1.0",
                cache_system=True,
            )
            match = re.search(r"\[.*\]", response.content, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as e:
            logger.warning("rule_card_extraction_failed", error=str(e))
        return []

    @staticmethod
    def _extract_key_terms(normalized_query: str, expanded_queries: list[str]) -> list[str]:
        """Extract Korean noun chunks for ILIKE search, including particle-stripped variants.
        Only uses the normalized query (not synonyms) to keep terms specific and avoid broad matches."""
        all_text = normalized_query  # Synonyms are too generic for ILIKE — use original query only
        # Generic question endings and common words that match too broadly
        stop = {
            "가능", "불가", "여부", "방법", "절차", "있나요", "합니까", "하나요",
            "입니다", "됩니다", "가능한가요", "가능한지", "됩니까", "되나요",
            "하면", "하는지", "해도", "할수", "할수있", "있을까요", "있는가요",
            "이란", "이란게", "무엇인가요", "어떻게", "어디서",
        }
        # Korean subject/object/topic particles to strip
        particles = ["이", "을", "를", "은", "는", "에", "의", "도", "로", "가", "와", "과"]
        tokens = re.findall(r"[가-힣]{2,8}", all_text)
        seen: set[str] = set()
        result: list[str] = []
        for t in tokens:
            candidates = [t]
            # Also try particle-stripped version
            for p in particles:
                if t.endswith(p) and len(t) > len(p) + 1:
                    candidates.append(t[: -len(p)])
            for c in candidates:
                if c not in stop and c not in seen and len(c) >= 2:
                    seen.add(c)
                    result.append(c)
            if len(result) >= 8:
                break
        return result[:8]

    @staticmethod
    def _doc_tier(chunk: dict) -> int:
        """
        tier_1: synced law/decree text (source_type == "legal")
        tier_2: official FAQ / operational guide uploaded by user
        tier_3: general educational manual / surrounding context
        """
        if chunk.get("source_type") == "legal":
            return 1
        name = (chunk.get("display_name") or chunk.get("original_filename") or "").lower()
        if any(p.lower() in name for p in _TIER2_FILENAME_PATTERNS):
            return 2
        return 3

    @staticmethod
    def _has_direct_answer(chunk: dict) -> bool:
        return bool(_DIRECT_ANSWER_RE.search(chunk.get("chunk_text", "")))

    def _assess_answerability(
        self,
        question_type: str,
        all_chunks: list[dict],
        rule_cards: list[dict],
    ) -> dict[str, Any]:
        if not all_chunks:
            return {
                "status": "not_found_in_uploaded_materials",
                "has_direct_evidence": False,
                "explanation": "업로드된 자료에서 관련 내용을 찾을 수 없습니다.",
            }

        max_conf = max(c["similarity"] for c in all_chunks)
        has_legal = any(c.get("source_type") == "legal" for c in all_chunks)
        has_rcms = any(c.get("source_type") == "rcms" for c in all_chunks)

        # ── tier_1: law rule cards with high confidence ──────────────────────
        high_conf_cards = [rc for rc in rule_cards if rc.get("confidence", 0) >= 0.75]
        if high_conf_cards and max_conf >= 0.70:
            return {
                "status": "answered_with_direct_evidence",
                "has_direct_evidence": True,
                "evidence_tier": 1,
                "explanation": f"법령 직접 근거 {len(high_conf_cards)}건 확인됨",
            }

        # ── tier_2: authoritative FAQ / official guide with direct answer ────
        tier2_direct = [
            c for c in all_chunks
            if self._doc_tier(c) == 2
            and c["similarity"] >= 0.45
            and self._has_direct_answer(c)
        ]
        if tier2_direct:
            return {
                "status": "answered_with_direct_evidence",
                "has_direct_evidence": True,
                "evidence_tier": 2,
                "explanation": (
                    f"공식 FAQ/운영안내에서 직접 답변 {len(tier2_direct)}건 확인됨 "
                    f"(최고 유사도 {max(c['similarity'] for c in tier2_direct):.2f})"
                ),
            }

        # ── tier_2: authoritative FAQ present even without pattern match ─────
        # 0.45 threshold: text-match results have fixed similarity=0.50
        tier2_any = [
            c for c in all_chunks
            if self._doc_tier(c) == 2 and c["similarity"] >= 0.45
        ]
        if tier2_any:
            return {
                "status": "answered_with_mixed_sources",
                "has_direct_evidence": True,
                "evidence_tier": 2,
                "explanation": "공식 FAQ/운영안내에서 관련 내용 확인됨",
            }

        # ── mixed tier_1 + tier_3 ────────────────────────────────────────────
        if has_legal and has_rcms and max_conf >= 0.55:
            return {
                "status": "answered_with_mixed_sources",
                "has_direct_evidence": False,
                "evidence_tier": 3,
                "explanation": "법령과 매뉴얼 두 소스에서 관련 내용 확인됨",
            }

        # ── related context only ─────────────────────────────────────────────
        if max_conf >= 0.45:
            return {
                "status": "related_context_only",
                "has_direct_evidence": False,
                "evidence_tier": 3,
                "explanation": "관련 맥락은 확인되나 직접적인 규정 문구는 불명확합니다.",
            }

        return {
            "status": "insufficient_evidence",
            "has_direct_evidence": False,
            "evidence_tier": 3,
            "explanation": "충분한 근거를 찾지 못했습니다.",
        }

    async def _generate_structured_answer(
        self,
        question: str,
        understanding: Any,
        rcms_chunks: list[dict],
        legal_chunks: list[dict],
        rule_cards: list[dict],
        answerability: dict[str, Any],
    ) -> dict[str, Any]:
        question_type = understanding.question_type
        answerability_status = answerability["status"]

        evidence_tier = answerability.get("evidence_tier", 3)

        # Build context: decisive tier_2 chunks first, then fill remaining slots
        decisive_rcms = [
            c for c in rcms_chunks
            if self._doc_tier(c) == 2 and self._has_direct_answer(c) and c["similarity"] >= 0.45
        ]
        other_rcms = [c for c in rcms_chunks if c not in decisive_rcms]
        # Prioritized order: decisive tier_2 → other rcms (up to 5 total)
        ordered_rcms = (decisive_rcms[:3] + other_rcms)[:5]

        context_parts: list[str] = []
        for i, c in enumerate(legal_chunks[:3]):
            context_parts.append(
                f"[법령 원문 {i+1}] {c.get('law_name', '')} "
                f"{c.get('article_number', '')} {c.get('article_title', '')}\n"
                f"{c['chunk_text']}"
            )
        for i, c in enumerate(ordered_rcms):
            tier = self._doc_tier(c)
            is_decisive = tier == 2 and self._has_direct_answer(c) and c["similarity"] >= 0.45
            if is_decisive:
                tier_label = "★직접답변★ 공식FAQ/운영안내"
            elif tier == 2:
                tier_label = "공식 FAQ/운영안내"
            else:
                tier_label = "참고 매뉴얼"
            context_parts.append(
                f"[{tier_label} {i+1}] {c.get('display_name', '')} "
                f"p.{c.get('page_number', '')}\n"
                f"{c['chunk_text']}"
            )

        # Rule card summary
        rule_card_text = ""
        if rule_cards:
            rule_card_text = "\n\n추출된 Rule Cards:\n" + json.dumps(
                rule_cards, ensure_ascii=False, indent=2
            )

        # Answerability notice — suppress warning when tier_2 evidence present
        if answerability["has_direct_evidence"]:
            answerability_notice = (
                f"\n\n[참고: {answerability['explanation']}]"
            )
        else:
            answerability_notice = (
                f"\n\n[주의: 판단 상태 = {answerability_status}] {answerability['explanation']}"
            )

        # Build format instructions by question type + evidence tier
        format_instructions = self._get_format_instructions(
            question_type, answerability_status, evidence_tier
        )

        user_msg = (
            f"다음 발췌문{rule_card_text and '과 Rule Card'}을 바탕으로 질문에 답변하세요."
            f"{answerability_notice}\n\n"
            f"{'=' * 50}\n"
            + "\n\n".join(context_parts)
            + f"\n{'=' * 50}\n\n"
            f"질문: {question}\n\n"
            + format_instructions
        )

        try:
            response = await self._llm.complete(
                system_prompt=EXPERT_SYSTEM_PROMPT,
                user_message=user_msg,
                prompt_version="expert-qa-2.0",
                cache_system=True,
            )
            parsed = self._parse_llm_json(response.content)
        except Exception as e:
            logger.error("answer_generation_failed", error=str(e))
            parsed = self._fallback_answer(question, answerability_status)

        # Build evidence list
        evidence = self._build_evidence(
            legal_chunks, rcms_chunks, rule_cards, parsed.get("used_source_indices", [])
        )

        # Determine final found_in_manual and answer_status
        found = answerability_status not in (
            "not_found_in_uploaded_materials",
            "routing_error",
            "insufficient_evidence",
        )

        model_version = self._llm._model

        return {
            "question_type": question_type,
            "short_answer": parsed.get("short_answer", ""),
            "conclusion": parsed.get("conclusion"),
            "conditions_or_exceptions": parsed.get("conditions_or_exceptions"),
            "legal_basis": parsed.get("legal_basis"),
            "rcms_steps": parsed.get("rcms_steps"),
            "detailed_explanation": parsed.get("detailed_explanation", ""),
            "further_confirmation_needed": parsed.get("further_confirmation_needed", False),
            "confidence": parsed.get("confidence", "low"),
            "evidence": evidence,
            "found_in_manual": found,
            "answer_status": answerability_status,
            "answer_status_type": answerability_status,
            "model_version": model_version,
            "prompt_version": "expert-qa-2.0",
        }

    def _get_format_instructions(
        self,
        question_type: str,
        answerability_status: str,
        evidence_tier: int = 3,
    ) -> str:
        # Only inject uncertainty when truly no direct evidence AND not from authoritative source
        uncertainty_note = ""
        if (
            answerability_status in ("related_context_only", "insufficient_evidence")
            and evidence_tier >= 3
        ):
            uncertainty_note = (
                '\n  "short_answer": "업로드된 자료에서 직접적인 규정 문구는 확인되지 않았습니다. '
                "관련 맥락은 확인되었지만, 확정적인 정책 근거로 보기 어렵습니다.\","
            )

        # Source label instruction for legal_policy answered by FAQ
        faq_note = ""
        if question_type in ("legal_policy", "mixed") and evidence_tier == 2:
            faq_note = '\n  "legal_basis": "공식 FAQ/운영안내 기준 - 출처명 기재",'

        if question_type == "legal_policy":
            return (
                "반드시 아래 JSON 형식으로만 응답하세요:\n"
                "{\n"
                f'  "short_answer": "핵심 결론 (2-3문장){uncertainty_note}",\n'
                '  "conclusion": "허용/불가/조건부허용/승인필요 - 이유",'
                f"{faq_note}\n"
                '  "conditions_or_exceptions": "조건 및 예외사항 (없으면 null)",\n'
                '  "legal_basis": "법령명 또는 FAQ출처 - 인용구 (없으면 null)",\n'
                '  "rcms_steps": null,\n'
                '  "detailed_explanation": "상세 설명",\n'
                '  "further_confirmation_needed": true/false,\n'
                '  "confidence": "high/medium/low",\n'
                '  "used_source_indices": [0, 1]\n'
                "}"
            )
        elif question_type == "rcms_procedure":
            return (
                "반드시 아래 JSON 형식으로만 응답하세요:\n"
                "{\n"
                '  "short_answer": "간단한 답변 (2-3문장)",\n'
                '  "conclusion": null,\n'
                '  "conditions_or_exceptions": null,\n'
                '  "legal_basis": null,\n'
                '  "rcms_steps": "1단계: ...\\n2단계: ...\\n3단계: ...",\n'
                '  "detailed_explanation": "상세 절차 설명",\n'
                '  "further_confirmation_needed": false,\n'
                '  "confidence": "high/medium/low",\n'
                '  "used_source_indices": [0]\n'
                "}"
            )
        elif question_type == "mixed":
            return (
                "반드시 아래 JSON 형식으로만 응답하세요:\n"
                "{\n"
                '  "short_answer": "결론 요약 (2-3문장)",\n'
                '  "conclusion": "허용/불가/조건부허용 - 이유",'
                f"{faq_note}\n"
                '  "conditions_or_exceptions": "조건 및 예외사항 (없으면 null)",\n'
                '  "legal_basis": "법령 또는 FAQ 근거 (없으면 null)",\n'
                '  "rcms_steps": "1단계: ...\\n2단계: ...\\n(없으면 null)",\n'
                '  "detailed_explanation": "통합 설명",\n'
                '  "further_confirmation_needed": true/false,\n'
                '  "confidence": "high/medium/low",\n'
                '  "used_source_indices": [0, 1]\n'
                "}"
            )
        else:  # definition
            return (
                "반드시 아래 JSON 형식으로만 응답하세요:\n"
                "{\n"
                '  "short_answer": "정의 요약",\n'
                '  "conclusion": null,\n'
                '  "conditions_or_exceptions": null,\n'
                '  "legal_basis": "출처 (있으면)",\n'
                '  "rcms_steps": null,\n'
                '  "detailed_explanation": "상세 설명 및 사용 맥락",\n'
                '  "further_confirmation_needed": false,\n'
                '  "confidence": "high/medium/low",\n'
                '  "used_source_indices": [0]\n'
                "}"
            )

    def _build_evidence(
        self,
        legal_chunks: list[dict],
        rcms_chunks: list[dict],
        rule_cards: list[dict],
        used_indices: list[int],
    ) -> list[dict[str, Any]]:
        evidence = []
        min_conf = 0.40

        # Legal evidence (tier_1)
        decisive_law_names = {
            rc.get("source_name", "") for rc in rule_cards if rc.get("confidence", 0) >= 0.70
        }
        for c in legal_chunks:
            if c["similarity"] < min_conf:
                continue
            is_decisive = c.get("law_name", "") in decisive_law_names
            evidence.append(
                {
                    "source_type": "legal",
                    "evidence_tier": 1,
                    "source_label": "법령 원문 근거",
                    "law_name": c.get("law_name"),
                    "article_number": c.get("article_number"),
                    "article_title": c.get("article_title"),
                    "page": None,
                    "section_title": c.get("section_title"),
                    "excerpt": c["chunk_text"][:400],
                    "confidence": round(c["similarity"], 4),
                    "chunk_id": c["chunk_id"],
                    "is_decisive": is_decisive,
                }
            )

        # RCMS evidence (tier_2 or tier_3)
        for c in rcms_chunks:
            if c["similarity"] < min_conf:
                continue
            tier = self._doc_tier(c)
            has_direct = self._has_direct_answer(c)
            # tier_2 with direct answer pattern → decisive
            is_decisive = tier == 2 and has_direct and c["similarity"] >= 0.45
            source_label = (
                "공식 FAQ/운영안내 근거" if tier == 2 else "일반 참고 문맥"
            )
            evidence.append(
                {
                    "source_type": "rcms",
                    "evidence_tier": tier,
                    "source_label": source_label,
                    "manual_id": c.get("manual_id"),
                    "display_name": c.get("display_name"),
                    "page": c.get("page_number"),
                    "section_title": c.get("section_title"),
                    "excerpt": c["chunk_text"][:400],
                    "confidence": round(c["similarity"], 4),
                    "chunk_id": c["chunk_id"],
                    "is_decisive": is_decisive,
                }
            )

        # Sort: decisive first, then by confidence
        evidence.sort(key=lambda e: (0 if e["is_decisive"] else 1, -e["confidence"]))
        return evidence

    def _parse_llm_json(self, content: str) -> dict[str, Any]:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        logger.warning("llm_json_parse_failed", preview=content[:200])
        return {
            "short_answer": content[:300],
            "detailed_explanation": content,
        }

    def _fallback_answer(self, question: str, status: str) -> dict[str, Any]:
        return {
            "short_answer": "답변 생성 중 오류가 발생했습니다.",
            "detailed_explanation": "잠시 후 다시 시도해 주세요.",
            "confidence": "low",
        }

    def _build_not_found_response(
        self, understanding: Any, debug_mode: bool
    ) -> dict[str, Any]:
        return {
            "question_type": understanding.question_type,
            "short_answer": "업로드된 자료에서 해당 내용을 찾을 수 없습니다.",
            "conclusion": None,
            "conditions_or_exceptions": None,
            "legal_basis": None,
            "rcms_steps": None,
            "detailed_explanation": (
                "업로드된 RCMS 매뉴얼 또는 법령에서 관련 내용을 찾지 못했습니다. "
                "관련 자료를 추가로 업로드하거나 질문을 수정해 주세요."
            ),
            "further_confirmation_needed": True,
            "confidence": "low",
            "evidence": [],
            "found_in_manual": False,
            "answer_status": "not_found_in_uploaded_materials",
            "answer_status_type": "not_found_in_uploaded_materials",
            "model_version": self._llm._model,
            "prompt_version": "expert-qa-2.0",
            "debug": None,
            "question_understanding": {
                "question_type": understanding.question_type,
                "normalized_query": understanding.normalized_query,
                "expanded_queries": understanding.expanded_queries,
                "routing_decision": understanding.routing_decision,
            },
            "retrieved_chunks": [],
        }
