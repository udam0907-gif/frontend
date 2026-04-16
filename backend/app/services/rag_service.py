from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import EmbeddingError, LLMServiceError, RagNoEvidenceError
from app.core.logging import get_logger
from app.models.rcms import RcmsChunk, RcmsQaSession
from app.services.llm_service import LLMService
from app.services.parser_service import ParserService

logger = get_logger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

ANSWER_STATUS_FOUND = "answered_with_evidence"
ANSWER_STATUS_NOT_FOUND = "not_found_in_uploaded_manuals"

# ─── Korean query normalization ──────────────────────────────────────────────

_PUNCT_RE = re.compile(r"[·•\-_/\\|,，。．]")
_WS_RE = re.compile(r"\s+")

# RCMS term synonyms: key → list of equivalent terms (key included)
RCMS_SYNONYMS: dict[str, list[str]] = {
    # 연구비 종류
    "연구비": ["연구비", "사업비", "연구개발비"],
    "사업비": ["연구비", "사업비", "연구개발비"],
    "연구개발비": ["연구비", "사업비", "연구개발비"],
    # 현황표
    "총괄현황표": ["총괄현황표", "총괄표", "현황표", "총괄 현황표"],
    "총괄표": ["총괄현황표", "총괄표", "현황표", "총괄 현황표"],
    "현황표": ["총괄현황표", "총괄표", "현황표", "총괄 현황표"],
    "총괄 현황표": ["총괄현황표", "총괄표", "현황표", "총괄 현황표"],
    # 등록/입력
    "등록": ["등록", "입력", "작성"],
    "입력": ["등록", "입력", "작성"],
    "작성": ["등록", "입력", "작성"],
    # 조회
    "조회": ["조회", "검색", "확인"],
    "검색": ["조회", "검색", "확인"],
    "확인": ["조회", "검색", "확인"],
    # 결재
    "승인": ["승인", "결재", "처리"],
    "결재": ["승인", "결재", "처리"],
    # 집행/지출
    "집행": ["집행", "지출", "사용"],
    "지출": ["집행", "지출", "사용"],
    # 정산
    "정산": ["정산", "결산", "마감"],
    "결산": ["정산", "결산", "마감"],
    # 예산 전용 (한도전용, 목적외 전용 등)
    "한도전용": ["한도전용", "전용", "예산전용", "항목전용", "타항목전용", "한도 전용"],
    "전용": ["전용", "한도전용", "예산전용", "항목전용"],
    "예산전용": ["예산전용", "한도전용", "전용", "항목전용"],
    "항목전용": ["항목전용", "한도전용", "전용", "타항목", "다른항목"],
    "타항목": ["타항목", "다른항목", "다른 항목", "타 항목"],
    "다른항목": ["다른항목", "타항목", "다른 항목", "타 항목"],
    # 편성
    "편성": ["편성", "배정", "할당", "책정"],
    "배정": ["배정", "편성", "할당", "책정"],
    # 신청
    "신청": ["신청", "요청", "접수"],
    "요청": ["신청", "요청", "접수"],
    # 취소/반려
    "취소": ["취소", "반려", "철회"],
    "반려": ["반려", "취소", "철회"],
    # 증빙
    "증빙": ["증빙", "영수증", "증빙서류", "첨부서류"],
    "영수증": ["영수증", "증빙", "증빙서류"],
}

# 오타 교정 맵: 자주 발생하는 한국어 오타 → 올바른 표현
TYPO_CORRECTIONS: dict[str, str] = {
    "다은항목": "다른항목",
    "다은 항목": "다른 항목",
    "한도 전용": "한도전용",
    "연구비전용": "연구비 전용",
    "예산 전용신청": "예산전용신청",
    "전용신청": "전용 신청",
    "정산신청": "정산 신청",
    "집행현황": "집행 현황",
    "비용청구": "비용 청구",
}

# Score assigned to chunks found only by keyword (not vector) search
KEYWORD_MATCH_SCORE = 0.60


def normalize_query(query: str) -> str:
    """
    Normalize Korean query text:
    - Convert punctuation to spaces
    - Collapse multiple whitespace
    - Apply typo corrections
    """
    q = _PUNCT_RE.sub(" ", query)
    q = _WS_RE.sub(" ", q).strip()
    # Apply typo corrections
    for typo, correction in TYPO_CORRECTIONS.items():
        q = q.replace(typo, correction)
    return q


def expand_query_terms(query: str) -> list[str]:
    """
    Return de-duplicated search variants for a query:
    - Original normalized form
    - Joined form (remove all spaces): 연구비 총괄 현황표 → 연구비총괄현황표
    - Synonym substitutions for known RCMS terms

    Example:
        "연구비 총괄 현황표 등록" →
        ["연구비 총괄 현황표 등록", "연구비총괄현황표등록",
         "사업비 총괄 현황표 등록", "연구개발비 총괄 현황표 등록",
         "연구비 총괄 현황표 입력", "연구비 총괄 현황표 작성", ...]
    """
    normalized = normalize_query(query)
    variants: set[str] = {normalized}

    # Add joined (no-space) form
    joined = normalized.replace(" ", "")
    if joined != normalized:
        variants.add(joined)

    # Synonym substitutions — iterate over a snapshot to avoid infinite growth
    base_variants = list(variants)
    for term, synonyms in RCMS_SYNONYMS.items():
        for base in base_variants:
            if term in base:
                for syn in synonyms:
                    if syn != term:
                        variants.add(base.replace(term, syn))

    return list(variants)


class RagService:
    """
    Closed-file RAG for RCMS manual Q&A.

    Rules (enforced in code, not just prompt):
    - Answers ONLY from retrieved chunks. No external knowledge.
    - If best hybrid similarity < threshold → returns explicit "not found" message.
    - Evidence always includes manual_id, display_name, page, section_title, excerpt.

    Retrieval pipeline:
    1. Normalize + expand query (whitespace, punctuation, synonyms)
    2. Vector search (pgvector cosine) on normalized query
    3. Keyword search (PostgreSQL ILIKE) on all expanded variants
    4. Merge + rerank: deduplicate by chunk_id, sort by score desc
    5. Return top N with debug info
    """

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service
        self._parser = ParserService()
        self._config = self._load_prompt_config()
        self._max_chunks = self._config.get("max_chunks", settings.rag_max_chunks)
        self._min_confidence = self._config.get("min_confidence", settings.rag_min_confidence)

    def _load_prompt_config(self) -> dict[str, Any]:
        # Prefer the new dual-source prompt; fall back to legacy
        for filename in ("rcms_dual_qa.yaml", "rcms_qa.yaml"):
            config_path = PROMPTS_DIR / filename
            try:
                with open(config_path, encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                    logger.info("prompt_config_loaded", file=filename, version=cfg.get("version"))
                    return cfg
            except FileNotFoundError:
                continue
        logger.warning("rcms_prompt_not_found")
        return {
            "system": (
                "당신은 RCMS(연구비 관리 시스템) 전문 도우미입니다. "
                "반드시 제공된 매뉴얼 내용만을 근거로 답변하세요."
            ),
            "version": "0.0.0",
            "max_chunks": 5,
            "min_confidence": 0.50,
        }

    # ─── Embedding ───────────────────────────────────────────────────────────

    async def embed_text(self, text: str) -> list[float]:
        if settings.embedding_provider == "local":
            return await self._embed_local(text)
        if settings.embedding_provider == "openai":
            return await self._embed_openai(text)
        raise EmbeddingError(f"지원하지 않는 임베딩 제공자: {settings.embedding_provider}")

    async def _embed_local(self, text: str) -> list[float]:
        """Local embedding using fastembed — no API key required, Korean supported."""
        import asyncio
        try:
            from fastembed import TextEmbedding
        except ImportError:
            raise EmbeddingError("fastembed가 설치되지 않았습니다. pip install fastembed")

        if not hasattr(self, "_fastembed"):
            self._fastembed = TextEmbedding(model_name=settings.embedding_model)

        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: list(self._fastembed.embed([text[:2048]])),
        )
        return embeddings[0].tolist()

    async def _embed_openai(self, text: str) -> list[float]:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            response = await client.embeddings.create(
                model=settings.embedding_model,
                input=text[:8191],
            )
            return response.data[0].embedding
        except Exception as e:
            raise EmbeddingError(f"OpenAI 임베딩 실패: {e}") from e

    # ─── Ingestion ───────────────────────────────────────────────────────────

    async def ingest_manual(
        self,
        db: AsyncSession,
        manual_id: uuid.UUID,
        file_path: str,
        filename: str,
    ) -> int:
        """
        Parse manual and store three retrieval granularities:
          1. chunks  — small overlapping windows (800 chars) for fine-grained search
          2. pages   — full page text as a single retrieval unit
          3. sections — heading-delimited blocks for policy/judgment questions

        Returns total chunk count (for backward compat with caller).
        """
        from app.models.rcms import RcmsPage, RcmsSection

        pages = self._parser.parse_file(file_path, filename)
        chunks_data = self._parser.chunk_text(
            pages,
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        )
        sections_data = self._parser.extract_sections(pages)

        # 1. Store chunks (existing behaviour — kept as fallback)
        stored_chunks = 0
        for chunk_data in chunks_data:
            embedding = await self.embed_text(chunk_data["chunk_text"])
            db.add(RcmsChunk(
                id=uuid.uuid4(),
                manual_id=manual_id,
                page_number=chunk_data["page_number"],
                section_title=chunk_data.get("section_title"),
                chunk_text=chunk_data["chunk_text"],
                chunk_index=chunk_data["chunk_index"],
                embedding=embedding,
            ))
            stored_chunks += 1

        # 2. Store pages
        stored_pages = 0
        for page in pages:
            if not page.text.strip():
                continue
            # Embed first 1500 chars (fits model input limit)
            embed_text = page.text[:1500]
            embedding = await self.embed_text(embed_text)
            db.add(RcmsPage(
                id=uuid.uuid4(),
                manual_id=manual_id,
                page_number=page.page_number,
                full_text=page.text,
                section_title=page.section_title,
                char_count=len(page.text),
                embedding=embedding,
            ))
            stored_pages += 1

        # 3. Store sections
        stored_sections = 0
        for sec in sections_data:
            if not sec["section_text"].strip():
                continue
            embed_text = sec["section_text"][:1500]
            embedding = await self.embed_text(embed_text)
            db.add(RcmsSection(
                id=uuid.uuid4(),
                manual_id=manual_id,
                page_number=sec["page_number"],
                section_title=sec["section_title"],
                section_text=sec["section_text"],
                section_index=sec["section_index"],
                embedding=embedding,
            ))
            stored_sections += 1

        await db.flush()
        logger.info(
            "manual_ingested",
            manual_id=str(manual_id),
            chunks=stored_chunks,
            pages=stored_pages,
            sections=stored_sections,
        )
        return stored_chunks, stored_pages, stored_sections

    # ─── Retrieval ───────────────────────────────────────────────────────────

    async def search_chunks(
        self,
        db: AsyncSession,
        query_embedding: list[float],
        manual_ids: list[uuid.UUID] | None = None,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Vector similarity search using pgvector cosine distance.
        Returns chunks enriched with manual display_name.
        """
        top_k = top_k or self._max_chunks
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        if manual_ids:
            id_list = ", ".join(f"'{str(mid)}'" for mid in manual_ids)
            where_clause = f"AND rc.manual_id IN ({id_list})"
        else:
            where_clause = ""

        sql = text(f"""
            SELECT
                rc.id,
                rc.manual_id,
                rm.display_name,
                rm.original_filename,
                rc.page_number,
                rc.section_title,
                rc.chunk_text,
                rc.chunk_index,
                1 - (rc.embedding <=> '{embedding_str}'::vector) AS similarity
            FROM rcms_chunks rc
            JOIN rcms_manuals rm ON rm.id = rc.manual_id
            WHERE rm.parse_status = 'completed'
            {where_clause}
            ORDER BY rc.embedding <=> '{embedding_str}'::vector
            LIMIT :top_k
        """)

        result = await db.execute(sql, {"top_k": top_k})
        rows = result.fetchall()

        return [
            {
                "chunk_id": str(row.id),
                "manual_id": str(row.manual_id),
                "display_name": row.display_name,
                "original_filename": row.original_filename,
                "page_number": row.page_number,
                "section_title": row.section_title,
                "chunk_text": row.chunk_text,
                "chunk_index": row.chunk_index,
                "similarity": float(row.similarity),
                "match_type": "vector",
            }
            for row in rows
        ]

    async def search_chunks_keyword(
        self,
        db: AsyncSession,
        terms: list[str],
        manual_ids: list[uuid.UUID] | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Keyword search using PostgreSQL ILIKE.
        Matches any chunk containing at least one of the given terms.
        Assigns a fixed KEYWORD_MATCH_SCORE to all results.
        """
        if not terms:
            return []

        # Build ILIKE conditions
        conditions = " OR ".join(
            f"rc.chunk_text ILIKE :term_{i}" for i in range(len(terms))
        )
        params: dict[str, Any] = {f"term_{i}": f"%{t}%" for i, t in enumerate(terms)}
        params["top_k"] = top_k

        if manual_ids:
            id_list = ", ".join(f"'{str(mid)}'" for mid in manual_ids)
            manual_filter = f"AND rc.manual_id IN ({id_list})"
        else:
            manual_filter = ""

        sql = text(f"""
            SELECT
                rc.id,
                rc.manual_id,
                rm.display_name,
                rm.original_filename,
                rc.page_number,
                rc.section_title,
                rc.chunk_text,
                rc.chunk_index
            FROM rcms_chunks rc
            JOIN rcms_manuals rm ON rm.id = rc.manual_id
            WHERE rm.parse_status = 'completed'
            {manual_filter}
            AND ({conditions})
            LIMIT :top_k
        """)

        result = await db.execute(sql, params)
        rows = result.fetchall()

        return [
            {
                "chunk_id": str(row.id),
                "manual_id": str(row.manual_id),
                "display_name": row.display_name,
                "original_filename": row.original_filename,
                "page_number": row.page_number,
                "section_title": row.section_title,
                "chunk_text": row.chunk_text,
                "chunk_index": row.chunk_index,
                "similarity": KEYWORD_MATCH_SCORE,
                "match_type": "keyword",
            }
            for row in rows
        ]

    async def search_pages(
        self,
        db: AsyncSession,
        query_embedding: list[float],
        terms: list[str],
        manual_ids: list[uuid.UUID] | None = None,
        top_k: int = 6,
    ) -> list[dict[str, Any]]:
        """Vector + keyword search on rcms_pages (full-page retrieval units)."""
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        manual_filter = ""
        if manual_ids:
            id_list = ", ".join(f"'{str(mid)}'" for mid in manual_ids)
            manual_filter = f"AND rp.manual_id IN ({id_list})"

        # Vector search
        sql_vec = text(f"""
            SELECT rp.id, rp.manual_id, rm.display_name, rm.original_filename,
                   rp.page_number, rp.section_title, rp.full_text, rp.char_count,
                   1 - (rp.embedding <=> '{embedding_str}'::vector) AS similarity
            FROM rcms_pages rp
            JOIN rcms_manuals rm ON rm.id = rp.manual_id
            WHERE rm.parse_status = 'completed' {manual_filter}
            ORDER BY rp.embedding <=> '{embedding_str}'::vector
            LIMIT :top_k
        """)
        rows_vec = (await db.execute(sql_vec, {"top_k": top_k})).fetchall()

        results: dict[str, dict[str, Any]] = {}
        for row in rows_vec:
            results[str(row.id)] = {
                "unit_id": str(row.id),
                "unit_type": "page",
                "manual_id": str(row.manual_id),
                "display_name": row.display_name,
                "page_number": row.page_number,
                "section_title": row.section_title,
                "context_text": row.full_text,
                "similarity": float(row.similarity),
                "match_type": "vector",
            }

        # Keyword search
        if terms:
            conditions = " OR ".join(f"rp.full_text ILIKE :term_{i}" for i in range(len(terms)))
            params: dict[str, Any] = {f"term_{i}": f"%{t}%" for i, t in enumerate(terms)}
            params["top_k"] = top_k
            sql_kw = text(f"""
                SELECT rp.id, rp.manual_id, rm.display_name, rm.original_filename,
                       rp.page_number, rp.section_title, rp.full_text
                FROM rcms_pages rp
                JOIN rcms_manuals rm ON rm.id = rp.manual_id
                WHERE rm.parse_status = 'completed' {manual_filter}
                AND ({conditions}) LIMIT :top_k
            """)
            rows_kw = (await db.execute(sql_kw, params)).fetchall()
            for row in rows_kw:
                uid = str(row.id)
                if uid not in results:
                    results[uid] = {
                        "unit_id": uid,
                        "unit_type": "page",
                        "manual_id": str(row.manual_id),
                        "display_name": row.display_name,
                        "page_number": row.page_number,
                        "section_title": row.section_title,
                        "context_text": row.full_text,
                        "similarity": KEYWORD_MATCH_SCORE,
                        "match_type": "keyword",
                    }
                else:
                    results[uid]["match_type"] = "hybrid"

        return list(results.values())

    async def search_sections(
        self,
        db: AsyncSession,
        query_embedding: list[float],
        terms: list[str],
        manual_ids: list[uuid.UUID] | None = None,
        top_k: int = 6,
    ) -> list[dict[str, Any]]:
        """Vector + keyword search on rcms_sections (section-level retrieval units)."""
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        manual_filter = ""
        if manual_ids:
            id_list = ", ".join(f"'{str(mid)}'" for mid in manual_ids)
            manual_filter = f"AND rs.manual_id IN ({id_list})"

        # Vector search
        sql_vec = text(f"""
            SELECT rs.id, rs.manual_id, rm.display_name, rm.original_filename,
                   rs.page_number, rs.section_title, rs.section_text,
                   1 - (rs.embedding <=> '{embedding_str}'::vector) AS similarity
            FROM rcms_sections rs
            JOIN rcms_manuals rm ON rm.id = rs.manual_id
            WHERE rm.parse_status = 'completed' {manual_filter}
            ORDER BY rs.embedding <=> '{embedding_str}'::vector
            LIMIT :top_k
        """)
        rows_vec = (await db.execute(sql_vec, {"top_k": top_k})).fetchall()

        results: dict[str, dict[str, Any]] = {}
        for row in rows_vec:
            results[str(row.id)] = {
                "unit_id": str(row.id),
                "unit_type": "section",
                "manual_id": str(row.manual_id),
                "display_name": row.display_name,
                "page_number": row.page_number,
                "section_title": row.section_title,
                "context_text": row.section_text,
                "similarity": float(row.similarity),
                "match_type": "vector",
            }

        # Keyword search
        if terms:
            conditions = " OR ".join(f"rs.section_text ILIKE :term_{i}" for i in range(len(terms)))
            params: dict[str, Any] = {f"term_{i}": f"%{t}%" for i, t in enumerate(terms)}
            params["top_k"] = top_k
            sql_kw = text(f"""
                SELECT rs.id, rs.manual_id, rm.display_name, rm.original_filename,
                       rs.page_number, rs.section_title, rs.section_text
                FROM rcms_sections rs
                JOIN rcms_manuals rm ON rm.id = rs.manual_id
                WHERE rm.parse_status = 'completed' {manual_filter}
                AND ({conditions}) LIMIT :top_k
            """)
            rows_kw = (await db.execute(sql_kw, params)).fetchall()
            for row in rows_kw:
                uid = str(row.id)
                if uid not in results:
                    results[uid] = {
                        "unit_id": uid,
                        "unit_type": "section",
                        "manual_id": str(row.manual_id),
                        "display_name": row.display_name,
                        "page_number": row.page_number,
                        "section_title": row.section_title,
                        "context_text": row.section_text,
                        "similarity": KEYWORD_MATCH_SCORE,
                        "match_type": "keyword",
                    }
                else:
                    results[uid]["match_type"] = "hybrid"

        return list(results.values())

    # ─── Question classification ─────────────────────────────────────────────

    # Substrings that strongly indicate a legal/regulatory question
    _LEGAL_SIGNALS = (
        "법", "시행령", "고시", "훈령", "규정", "법령", "조항", "조문", "기준",
        "허용", "불가", "금지", "위반", "처벌", "제재",
        "법적", "규정상", "합법", "적법", "여부", "가부",
        "혁신법", "사용기준", "이행", "의무",
        "가능한가", "가능합니까", "가능한지",
        "해석", "판단기준", "적용", "준수", "근거법",
        "국가연구개발",
    )

    # Substrings that strongly indicate an RCMS system usage question
    _RCMS_SIGNALS = (
        "rcms", "시스템", "메뉴", "화면", "버튼", "클릭",
        "등록방법", "입력방법", "어떻게 등록", "어떻게 입력",
        "절차", "단계", "순서", "방법은",
        "로그인", "업로드", "다운로드",
        "팝업", "탭에서", "화면에서",
        "총괄현황표", "집행등록", "정산신청",
    )

    def classify_question(self, question: str) -> str:
        """
        Classify question into: rcms_procedure | legal_policy | mixed.

        Uses a keyword heuristic — fast, no LLM call.
        Returns 'rcms_procedure' as default (safest fallback: search RCMS first).
        """
        q = question.lower()
        has_legal = any(sig in q for sig in self._LEGAL_SIGNALS)
        has_rcms = any(sig in q for sig in self._RCMS_SIGNALS)

        if has_legal and has_rcms:
            return "mixed"
        if has_legal:
            return "legal_policy"
        return "rcms_procedure"

    # ─── Legal chunk search ──────────────────────────────────────────────────

    async def search_legal(
        self,
        db: AsyncSession,
        question: str,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Hybrid vector + keyword search on legal_chunks.
        Returns results tagged with source_type='legal'.
        """
        top_k = top_k or self._max_chunks
        normalized = normalize_query(question)
        variants = expand_query_terms(question)
        query_embedding = await self.embed_text(normalized)
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # Vector search
        sql_vec = text(f"""
            SELECT lc.id, lc.document_id, ld.law_name,
                   lc.article_number, lc.article_title,
                   lc.chunk_text, lc.chunk_index,
                   1 - (lc.embedding <=> '{embedding_str}'::vector) AS similarity
            FROM legal_chunks lc
            JOIN legal_documents ld ON ld.id = lc.document_id
            WHERE ld.sync_status = 'completed'
            ORDER BY lc.embedding <=> '{embedding_str}'::vector
            LIMIT :top_k
        """)
        rows_vec = (await db.execute(sql_vec, {"top_k": top_k * 2})).fetchall()

        results: dict[str, dict[str, Any]] = {}
        for row in rows_vec:
            results[str(row.id)] = {
                "chunk_id": str(row.id),
                "source_type": "legal",
                "document_id": str(row.document_id),
                "law_name": row.law_name,
                "article_number": row.article_number,
                "article_title": row.article_title,
                "chunk_text": row.chunk_text,
                "context_text": row.chunk_text,
                "similarity": float(row.similarity),
                "match_type": "vector",
            }

        # Keyword search
        if variants:
            conditions = " OR ".join(
                f"lc.chunk_text ILIKE :term_{i}" for i in range(len(variants))
            )
            params: dict[str, Any] = {f"term_{i}": f"%{t}%" for i, t in enumerate(variants)}
            params["top_k"] = top_k * 2
            sql_kw = text(f"""
                SELECT lc.id, lc.document_id, ld.law_name,
                       lc.article_number, lc.article_title, lc.chunk_text
                FROM legal_chunks lc
                JOIN legal_documents ld ON ld.id = lc.document_id
                WHERE ld.sync_status = 'completed'
                AND ({conditions})
                LIMIT :top_k
            """)
            rows_kw = (await db.execute(sql_kw, params)).fetchall()
            for row in rows_kw:
                uid = str(row.id)
                if uid not in results:
                    results[uid] = {
                        "chunk_id": uid,
                        "source_type": "legal",
                        "document_id": str(row.document_id),
                        "law_name": row.law_name,
                        "article_number": row.article_number,
                        "article_title": row.article_title,
                        "chunk_text": row.chunk_text,
                        "context_text": row.chunk_text,
                        "similarity": KEYWORD_MATCH_SCORE,
                        "match_type": "keyword",
                    }
                else:
                    results[uid]["match_type"] = "hybrid"

        ranked = sorted(results.values(), key=lambda x: x["similarity"], reverse=True)
        logger.info(
            "legal_search_results",
            question=question[:60],
            hits=len(ranked),
            top_score=round(ranked[0]["similarity"], 4) if ranked else 0,
        )
        return ranked[:top_k]

    async def hybrid_search(
        self,
        db: AsyncSession,
        question: str,
        manual_ids: list[uuid.UUID] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        3-level hybrid retrieval: sections → pages → chunks (fallback).

        Priority:
          - Sections preferred for policy/judgment questions (heading context preserved)
          - Pages preferred when sections have low coverage
          - Chunks kept as fallback for manuals ingested before upgrade

        Returns:
            (top_results, debug_candidates)
        """
        normalized = normalize_query(question)
        variants = expand_query_terms(question)
        top_k = self._max_chunks

        logger.info(
            "hybrid_search_start",
            original=question[:80],
            normalized=normalized[:80],
            variant_count=len(variants),
        )

        query_embedding = await self.embed_text(normalized)

        # ── Level 1: Section search (best for policy/judgment questions) ──────
        section_results = await self.search_sections(
            db, query_embedding, variants, manual_ids, top_k=top_k * 2
        )

        # ── Level 2: Page search (broad context) ──────────────────────────────
        page_results = await self.search_pages(
            db, query_embedding, variants, manual_ids, top_k=top_k * 2
        )

        # ── Level 3: Chunk search (fallback for legacy manuals) ───────────────
        chunk_vec = await self.search_chunks(
            db, query_embedding, manual_ids, top_k=top_k * 2
        )
        chunk_kw = await self.search_chunks_keyword(
            db, variants, manual_ids, top_k=top_k * 2
        )
        # Merge chunk results
        chunk_merged: dict[str, dict[str, Any]] = {}
        for c in chunk_vec:
            chunk_merged[c["chunk_id"]] = {**c, "unit_type": "chunk", "context_text": c["chunk_text"]}
        for c in chunk_kw:
            cid = c["chunk_id"]
            if cid in chunk_merged:
                chunk_merged[cid]["match_type"] = "hybrid"
            else:
                chunk_merged[cid] = {**c, "unit_type": "chunk", "context_text": c["chunk_text"]}
        chunk_results = list(chunk_merged.values())

        # ── Merge all levels, deduplicate by (manual_id, page_number) ─────────
        # Priority: section > page > chunk (sections carry heading context)
        # Use (manual_id, page_number) as dedup key for context building
        page_key_scores: dict[tuple[str, int], dict[str, Any]] = {}

        def _register(result: dict[str, Any], priority: int) -> None:
            """Register result, keeping highest-score per page with priority."""
            key = (result["manual_id"], result["page_number"])
            existing = page_key_scores.get(key)
            if existing is None:
                page_key_scores[key] = {**result, "_priority": priority}
            else:
                # Higher score always wins; break ties by priority (lower = better)
                if result["similarity"] > existing["similarity"] or (
                    result["similarity"] == existing["similarity"]
                    and priority < existing["_priority"]
                ):
                    page_key_scores[key] = {**result, "_priority": priority}

        for r in section_results:
            _register(r, priority=1)
        for r in page_results:
            _register(r, priority=2)
        for r in chunk_results:
            _register(r, priority=3)

        ranked = sorted(page_key_scores.values(), key=lambda x: x["similarity"], reverse=True)
        debug_candidates = ranked[:5]

        logger.info(
            "hybrid_search_results",
            section_hits=len(section_results),
            page_hits=len(page_results),
            chunk_hits=len(chunk_results),
            merged_pages=len(ranked),
            top_score=round(ranked[0]["similarity"], 4) if ranked else 0,
            debug_top5=[
                {
                    "display_name": c["display_name"],
                    "page": c["page_number"],
                    "unit_type": c.get("unit_type"),
                    "section": c.get("section_title"),
                    "score": round(c["similarity"], 4),
                    "match_type": c["match_type"],
                }
                for c in debug_candidates
            ],
        )

        return ranked[:top_k], debug_candidates

    # ─── Answer generation ───────────────────────────────────────────────────

    async def answer(
        self,
        db: AsyncSession,
        question: str,
        manual_ids: list[uuid.UUID] | None = None,
    ) -> dict[str, Any]:
        """
        Dual-source RAG pipeline.

        1. Classify question → rcms_procedure | legal_policy | mixed
        2. Search appropriate source(s) based on type
        3. Build tagged context ([법령] / [매뉴얼])
        4. Generate answer with dual-source prompt
        5. Return structured response with evidence separated by source_type
        """
        q_type = self.classify_question(question)

        legal_chunks: list[dict[str, Any]] = []
        rcms_chunks: list[dict[str, Any]] = []
        rcms_debug: list[dict[str, Any]] = []

        # Retrieve from legal layer
        if q_type in ("legal_policy", "mixed"):
            legal_chunks = await self.search_legal(db, question)

        # Retrieve from RCMS layer
        if q_type in ("rcms_procedure", "mixed"):
            rcms_chunks, rcms_debug = await self.hybrid_search(db, question, manual_ids)

        # Combine for confidence check
        all_chunks = legal_chunks + rcms_chunks
        debug_candidates = (
            _format_debug_candidates(rcms_debug) if rcms_debug
            else _format_legal_debug_candidates(legal_chunks[:5])
        )

        if not all_chunks:
            logger.warning("rag_no_chunks_found", question=question[:100], q_type=q_type)
            return self._not_found_response(q_type=q_type, debug_candidates=[])

        max_confidence = max(c["similarity"] for c in all_chunks)
        if max_confidence < self._min_confidence:
            logger.info(
                "rag_below_confidence_threshold",
                max_confidence=round(max_confidence, 4),
                threshold=self._min_confidence,
                q_type=q_type,
            )
            return self._not_found_response(q_type=q_type, debug_candidates=debug_candidates)

        # ── Build dual-tagged context ──────────────────────────────────────────
        context_parts: list[str] = []
        all_indexed_chunks: list[dict[str, Any]] = []

        for chunk in legal_chunks:
            idx = len(all_indexed_chunks)
            art_ref = ""
            if chunk.get("article_number"):
                art_ref = chunk["article_number"]
                if chunk.get("article_title"):
                    art_ref += f" {chunk['article_title']}"
            context_parts.append(
                f"[법령] {chunk['law_name']} {art_ref} (근거 {idx + 1})\n"
                f"{chunk['context_text'][:2000]}"
            )
            all_indexed_chunks.append(chunk)

        for result in rcms_chunks:
            idx = len(all_indexed_chunks)
            unit_label = {
                "section": f"섹션: {result.get('section_title', '')}",
                "page": f"페이지: {result.get('section_title', '')}",
                "chunk": f"발췌: {result.get('section_title', '')}",
            }.get(result.get("unit_type", "chunk"), "발췌")
            context_parts.append(
                f"[매뉴얼] {result['display_name']} | p.{result['page_number']} | {unit_label} (근거 {idx + 1})\n"
                f"{result.get('context_text', result.get('chunk_text', ''))[:2000]}"
            )
            all_indexed_chunks.append(result)

        # ── Call LLM ──────────────────────────────────────────────────────────
        system_prompt = self._config.get("system", "")
        prompt_version = self._config.get("version", "unknown")

        user_msg = (
            f"질문 유형: {q_type}\n\n"
            "아래 소스 발췌만을 근거로 답변하세요. 발췌에 없는 내용은 절대 추측하지 마세요.\n"
            f"{'=' * 60}\n"
            + "\n\n".join(context_parts)
            + f"\n{'=' * 60}\n\n"
            f"질문: {question}\n\n"
            "반드시 아래 JSON 형식으로만 응답하세요 (JSON 외 텍스트 없이):\n"
            "{\n"
            '  "question_type": "rcms_procedure | legal_policy | mixed",\n'
            '  "short_answer": "2-3문장 핵심 요약",\n'
            '  "conclusion": "법적 결론 (legal_policy/mixed만 작성, 아니면 null)",\n'
            '  "legal_basis": "인용 법령·조문 (legal_policy/mixed만 작성, 아니면 null)",\n'
            '  "rcms_steps": "RCMS 처리 절차 (rcms_procedure/mixed만 작성, 아니면 null)",\n'
            '  "detailed_explanation": "소스 발췌 기반 상세 설명",\n'
            '  "evidence_indices": [0, 1, 2],\n'
            '  "found_in_manual": true\n'
            "}\n"
            "evidence_indices: 위 근거 번호(0-based) 중 실제 답변에 사용한 것들."
        )

        response = await self._llm.complete(
            system_prompt=system_prompt,
            user_message=user_msg,
            prompt_version=prompt_version,
            cache_system=True,
        )

        parsed = self._parse_llm_response(response.content)

        used_indices = parsed.get("evidence_indices", [])
        if not isinstance(used_indices, list):
            used_indices = []
        if not used_indices:
            used_indices = [
                i for i, c in enumerate(all_indexed_chunks)
                if c["similarity"] >= self._min_confidence
            ]

        # ── Build evidence items ───────────────────────────────────────────────
        evidence: list[dict[str, Any]] = []
        for idx in used_indices:
            if 0 <= idx < len(all_indexed_chunks):
                c = all_indexed_chunks[idx]
                if c.get("source_type") == "legal":
                    evidence.append({
                        "source_type": "legal",
                        "law_name": c.get("law_name"),
                        "article_number": c.get("article_number"),
                        "article_title": c.get("article_title"),
                        "excerpt": c["context_text"][:400],
                        "confidence": round(c["similarity"], 4),
                        "chunk_id": c.get("chunk_id"),
                    })
                else:
                    ctx = c.get("context_text", c.get("chunk_text", ""))
                    evidence.append({
                        "source_type": "rcms",
                        "manual_id": c["manual_id"],
                        "display_name": c["display_name"],
                        "page": c["page_number"],
                        "section_title": c.get("section_title"),
                        "excerpt": ctx[:400],
                        "confidence": round(c["similarity"], 4),
                        "chunk_id": c.get("unit_id", c.get("chunk_id", "")),
                    })

        if not evidence and all_indexed_chunks:
            best = all_indexed_chunks[0]
            if best.get("source_type") == "legal":
                evidence.append({
                    "source_type": "legal",
                    "law_name": best.get("law_name"),
                    "article_number": best.get("article_number"),
                    "article_title": best.get("article_title"),
                    "excerpt": best["context_text"][:400],
                    "confidence": round(best["similarity"], 4),
                    "chunk_id": best.get("chunk_id"),
                })
            else:
                ctx = best.get("context_text", best.get("chunk_text", ""))
                evidence.append({
                    "source_type": "rcms",
                    "manual_id": best["manual_id"],
                    "display_name": best["display_name"],
                    "page": best["page_number"],
                    "section_title": best.get("section_title"),
                    "excerpt": ctx[:400],
                    "confidence": round(best["similarity"], 4),
                    "chunk_id": best.get("unit_id", best.get("chunk_id", "")),
                })

        answer_status = ANSWER_STATUS_FOUND if evidence else ANSWER_STATUS_NOT_FOUND

        return {
            "question_type": parsed.get("question_type", q_type),
            "short_answer": parsed.get("short_answer", ""),
            "conclusion": parsed.get("conclusion"),
            "legal_basis": parsed.get("legal_basis"),
            "rcms_steps": parsed.get("rcms_steps"),
            "detailed_explanation": parsed.get("detailed_explanation", ""),
            "evidence": evidence,
            "found_in_manual": bool(evidence),
            "answer_status": answer_status,
            "model_version": response.model_version,
            "prompt_version": response.prompt_version,
            "token_usage": response.token_usage,
            "retrieved_chunks": [
                {
                    "chunk_id": c.get("unit_id", c.get("chunk_id", "")),
                    "source_type": c.get("source_type", "rcms"),
                    "unit_type": c.get("unit_type", "chunk"),
                    "display_name": c.get("display_name") or c.get("law_name", ""),
                    "page_number": c.get("page_number"),
                    "similarity": round(c["similarity"], 4),
                    "match_type": c["match_type"],
                }
                for c in all_indexed_chunks
            ],
            "debug_candidates": debug_candidates,
        }

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _parse_llm_response(self, content: str) -> dict[str, Any]:
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        logger.warning("rag_json_parse_failed", content_preview=content[:200])
        return {
            "short_answer": content[:500],
            "detailed_explanation": content,
            "evidence_indices": [],
            "found_in_manual": True,
        }

    def _not_found_response(
        self,
        debug_candidates: list[dict[str, Any]],
        q_type: str = "rcms_procedure",
    ) -> dict[str, Any]:
        return {
            "question_type": q_type,
            "short_answer": "업로드된 매뉴얼 및 등록된 법령에서 해당 내용을 찾을 수 없습니다.",
            "conclusion": None,
            "legal_basis": None,
            "rcms_steps": None,
            "detailed_explanation": (
                "질문에 해당하는 내용이 현재 업로드된 RCMS 매뉴얼 또는 등록된 법령에 "
                "존재하지 않습니다. 관련 매뉴얼을 추가 업로드하거나 법령을 동기화해 주세요."
            ),
            "evidence": [],
            "found_in_manual": False,
            "answer_status": ANSWER_STATUS_NOT_FOUND,
            "model_version": self._llm._model,
            "prompt_version": self._config.get("version", "unknown"),
            "token_usage": {},
            "retrieved_chunks": [],
            "debug_candidates": debug_candidates,
        }


def _format_debug_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Format top-5 RCMS retrieval candidates for debug output."""
    return [
        {
            "rank": i + 1,
            "source_type": "rcms",
            "unit_type": c.get("unit_type", "chunk"),
            "display_name": c["display_name"],
            "page": c["page_number"],
            "section_title": c.get("section_title"),
            "similarity": round(c["similarity"], 4),
            "match_type": c["match_type"],
            "excerpt": c.get("context_text", c.get("chunk_text", ""))[:300],
        }
        for i, c in enumerate(candidates)
    ]


def _format_legal_debug_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Format top-5 legal retrieval candidates for debug output."""
    return [
        {
            "rank": i + 1,
            "source_type": "legal",
            "unit_type": "legal_chunk",
            "display_name": c.get("law_name", ""),
            "page": None,
            "section_title": c.get("article_number"),
            "similarity": round(c["similarity"], 4),
            "match_type": c["match_type"],
            "excerpt": c.get("context_text", "")[:300],
        }
        for i, c in enumerate(candidates)
    ]
