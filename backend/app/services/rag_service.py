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


class RagService:
    """
    Closed-file RAG for RCMS manual Q&A.

    Rules (enforced in code, not just prompt):
    - Answers ONLY from retrieved chunks. No external knowledge.
    - If max vector similarity < threshold → returns explicit "not found" message.
    - Evidence always includes manual_id, display_name, page, section_title, excerpt.
    """

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service
        self._parser = ParserService()
        self._config = self._load_prompt_config()
        self._max_chunks = self._config.get("max_chunks", settings.rag_max_chunks)
        self._min_confidence = self._config.get("min_confidence", settings.rag_min_confidence)

    def _load_prompt_config(self) -> dict[str, Any]:
        config_path = PROMPTS_DIR / "rcms_qa.yaml"
        try:
            with open(config_path, encoding="utf-8") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning("rcms_qa_prompt_not_found", path=str(config_path))
            return {
                "system": (
                    "당신은 RCMS(연구비 관리 시스템) 전문 도우미입니다. "
                    "반드시 제공된 매뉴얼 내용만을 근거로 답변하세요."
                ),
                "version": "0.0.0",
                "max_chunks": 5,
                "min_confidence": 0.75,
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

        # Lazy-init: model is downloaded once and cached on disk (~120MB)
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
        """Parse manual, chunk, embed, and store in DB. Returns chunk count."""
        pages = self._parser.parse_file(file_path, filename)
        chunks = self._parser.chunk_text(
            pages,
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        )

        stored = 0
        for chunk_data in chunks:
            embedding = await self.embed_text(chunk_data["chunk_text"])
            chunk = RcmsChunk(
                id=uuid.uuid4(),
                manual_id=manual_id,
                page_number=chunk_data["page_number"],
                section_title=chunk_data.get("section_title"),
                chunk_text=chunk_data["chunk_text"],
                chunk_index=chunk_data["chunk_index"],
                embedding=embedding,
            )
            db.add(chunk)
            stored += 1

        await db.flush()
        logger.info("manual_ingested", manual_id=str(manual_id), chunks=stored)
        return stored

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
            }
            for row in rows
        ]

    async def text_match_chunks(
        self,
        db: AsyncSession,
        terms: list[str],
        manual_ids: list[uuid.UUID] | None = None,
        top_k: int = 4,
    ) -> list[dict[str, Any]]:
        """ILIKE text match search — finds chunks even through OCR noise."""
        if not terms:
            return []
        if manual_ids:
            id_list = ", ".join(f"'{str(mid)}'" for mid in manual_ids)
            where_extra = f"AND rc.manual_id IN ({id_list})"
        else:
            where_extra = ""

        conditions = " OR ".join(f"rc.chunk_text ILIKE :term{i}" for i in range(len(terms)))
        sql = text(f"""
            SELECT rc.id, rc.manual_id, rm.display_name, rm.original_filename,
                   rc.page_number, rc.section_title, rc.chunk_text, rc.chunk_index
            FROM rcms_chunks rc
            JOIN rcms_manuals rm ON rm.id = rc.manual_id
            WHERE rm.parse_status = 'completed'
              AND ({conditions})
              {where_extra}
            ORDER BY
                CASE WHEN rm.display_name ILIKE '%자주묻는%' OR rm.display_name ILIKE '%faq%'
                          OR rm.display_name ILIKE '%운영안내%' OR rm.display_name ILIKE '%업무안내%'
                     THEN 0 ELSE 1 END,
                rc.page_number
            LIMIT :top_k
        """)
        params: dict = {"top_k": top_k}
        for i, term in enumerate(terms):
            params[f"term{i}"] = f"%{term}%"
        try:
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
                    "similarity": 0.50,  # fixed score for text-match results
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning("rcms_text_match_failed", error=str(e))
            return []

    async def keyword_search_chunks(
        self,
        db: AsyncSession,
        queries: list[str],
        manual_ids: list[uuid.UUID] | None = None,
        top_k: int = 4,
    ) -> list[dict[str, Any]]:
        """pg_trgm keyword search for RCMS chunks — catches OCR-noisy FAQ content."""
        if not queries:
            return []
        query_str = queries[0]
        if manual_ids:
            id_list = ", ".join(f"'{str(mid)}'" for mid in manual_ids)
            where_extra = f"AND rc.manual_id IN ({id_list})"
        else:
            where_extra = ""
        sql = text(f"""
            SELECT
                rc.id, rc.manual_id, rm.display_name, rm.original_filename,
                rc.page_number, rc.section_title, rc.chunk_text, rc.chunk_index,
                similarity(rc.chunk_text, :query) AS sim_score
            FROM rcms_chunks rc
            JOIN rcms_manuals rm ON rm.id = rc.manual_id
            WHERE rm.parse_status = 'completed'
              AND rc.chunk_text % :query
              {where_extra}
            ORDER BY sim_score DESC
            LIMIT :top_k
        """)
        try:
            result = await db.execute(sql, {"query": query_str, "top_k": top_k})
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
                    "similarity": float(row.sim_score),
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning("rcms_keyword_search_failed", error=str(e))
            return []

    # ─── Answer generation ───────────────────────────────────────────────────

    async def answer(
        self,
        db: AsyncSession,
        question: str,
        manual_ids: list[uuid.UUID] | None = None,
    ) -> dict[str, Any]:
        """
        Full RAG pipeline: embed → search → generate with strict evidence-only policy.

        If max confidence < threshold: returns NOT_FOUND response without LLM call.
        Evidence items are always enriched from the vector search results (not just LLM output).
        """
        query_embedding = await self.embed_text(question)
        chunks = await self.search_chunks(db, query_embedding, manual_ids)

        if not chunks:
            logger.warning("rag_no_chunks_found", question=question[:100])
            return self._not_found_response()

        max_confidence = max(c["similarity"] for c in chunks)
        if max_confidence < self._min_confidence:
            logger.info(
                "rag_below_confidence_threshold",
                max_confidence=round(max_confidence, 4),
                threshold=self._min_confidence,
            )
            return self._not_found_response()

        # Build context string for the LLM
        context_parts = []
        for i, chunk in enumerate(chunks):
            context_parts.append(
                f"[발췌 {i+1}] 매뉴얼: {chunk['display_name']} | "
                f"페이지: {chunk['page_number']} | "
                f"섹션: {chunk['section_title'] or '제목 없음'}\n"
                f"{chunk['chunk_text']}"
            )

        system_prompt = self._config.get("system", "")
        prompt_version = self._config.get("version", "unknown")

        user_msg = (
            "아래 RCMS 매뉴얼 발췌문만을 근거로 질문에 답변하세요.\n"
            "발췌문에 없는 내용은 절대 추측하거나 보충하지 마세요.\n\n"
            f"{'=' * 60}\n"
            + "\n\n".join(context_parts)
            + f"\n{'=' * 60}\n\n"
            f"질문: {question}\n\n"
            "반드시 아래 JSON 형식으로만 응답하세요 (JSON 외 텍스트 없이):\n"
            "{\n"
            '  "short_answer": "간단한 답변 (2-3문장, 발췌문 근거만 사용)",\n'
            '  "detailed_explanation": "발췌문을 인용한 상세 설명",\n'
            '  "evidence_indices": [0, 1, 2],\n'
            '  "found_in_manual": true\n'
            "}\n\n"
            "evidence_indices는 위 발췌문 번호(0-based) 중 실제로 답변에 사용한 것들입니다."
        )

        response = await self._llm.complete(
            system_prompt=system_prompt,
            user_message=user_msg,
            prompt_version=prompt_version,
            cache_system=True,
        )

        parsed = self._parse_llm_response(response.content)

        # Build evidence from the vector search results (not LLM output)
        # This ensures evidence is always grounded in actual retrieved chunks
        used_indices = parsed.get("evidence_indices", [])
        if not isinstance(used_indices, list):
            used_indices = []

        # If LLM didn't specify indices, use all retrieved chunks above threshold
        if not used_indices:
            used_indices = [
                i for i, c in enumerate(chunks)
                if c["similarity"] >= self._min_confidence
            ]

        evidence = []
        for idx in used_indices:
            if 0 <= idx < len(chunks):
                c = chunks[idx]
                evidence.append({
                    "manual_id": c["manual_id"],
                    "display_name": c["display_name"],
                    "page": c["page_number"],
                    "section_title": c["section_title"],
                    "excerpt": c["chunk_text"][:400],  # cap excerpt length
                    "confidence": round(c["similarity"], 4),
                    "chunk_id": c["chunk_id"],
                })

        # Fallback: at least one evidence item from best chunk
        if not evidence and chunks:
            best = chunks[0]
            evidence.append({
                "manual_id": best["manual_id"],
                "display_name": best["display_name"],
                "page": best["page_number"],
                "section_title": best["section_title"],
                "excerpt": best["chunk_text"][:400],
                "confidence": round(best["similarity"], 4),
                "chunk_id": best["chunk_id"],
            })

        answer_status = ANSWER_STATUS_FOUND if evidence else ANSWER_STATUS_NOT_FOUND

        return {
            "short_answer": parsed.get("short_answer", ""),
            "detailed_explanation": parsed.get("detailed_explanation", ""),
            "evidence": evidence,
            "found_in_manual": True,
            "answer_status": answer_status,
            "model_version": response.model_version,
            "prompt_version": response.prompt_version,
            "token_usage": response.token_usage,
            "retrieved_chunks": [
                {
                    "chunk_id": c["chunk_id"],
                    "manual_id": c["manual_id"],
                    "display_name": c["display_name"],
                    "page_number": c["page_number"],
                    "similarity": c["similarity"],
                }
                for c in chunks
            ],
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

    def _not_found_response(self) -> dict[str, Any]:
        return {
            "short_answer": "업로드된 RCMS 매뉴얼에서 해당 내용을 찾을 수 없습니다.",
            "detailed_explanation": (
                "질문에 해당하는 내용이 현재 업로드된 RCMS 매뉴얼에 존재하지 않습니다. "
                "관련 매뉴얼을 추가로 업로드하거나 질문을 수정해 주세요."
            ),
            "evidence": [],
            "found_in_manual": False,
            "answer_status": ANSWER_STATUS_NOT_FOUND,
            "model_version": self._llm._model,
            "prompt_version": self._config.get("version", "unknown"),
            "token_usage": {},
            "retrieved_chunks": [],
        }
