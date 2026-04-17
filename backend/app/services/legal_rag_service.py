from __future__ import annotations

import re
import uuid
from typing import Any

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.models.enums import ParseStatus
from app.models.legal import LegalChunk, LegalDoc
from app.services.rag_service import RagService

logger = get_logger(__name__)

DEFAULT_LAWS = [
    "국가연구개발혁신법",
    "국가연구개발혁신법 시행령",
    "국가연구개발사업 연구개발비 사용 기준",
]

LAW_SEARCH_URL = "https://www.law.go.kr/DRF/lawSearch.do"
LAW_SERVICE_URL = "https://www.law.go.kr/DRF/lawService.do"


class LegalRagService:
    def __init__(self, rag_service: RagService) -> None:
        self._rag = rag_service

    async def list_docs(self, db: AsyncSession) -> list[LegalDoc]:
        result = await db.execute(select(LegalDoc).order_by(LegalDoc.created_at.desc()))
        return list(result.scalars().all())

    async def sync_law(self, db: AsyncSession, law_name: str, law_mst: str | None = None) -> LegalDoc:
        # Check if already exists
        result = await db.execute(select(LegalDoc).where(LegalDoc.law_name == law_name))
        existing = result.scalar_one_or_none()
        if existing:
            existing.sync_status = ParseStatus.pending
            existing.sync_error = None
            await db.flush()
            return existing

        doc = LegalDoc(
            id=uuid.uuid4(),
            law_name=law_name,
            law_mst=law_mst,
            source_type="api",
            sync_status=ParseStatus.pending,
            metadata_={},
        )
        db.add(doc)
        await db.flush()
        await db.refresh(doc)
        logger.info("legal_doc_created", law_name=law_name, doc_id=str(doc.id))
        return doc

    async def sync_defaults(self, db: AsyncSession) -> list[LegalDoc]:
        docs = []
        for law_name in DEFAULT_LAWS:
            doc = await self.sync_law(db, law_name)
            docs.append(doc)
        return docs

    async def delete_doc(self, db: AsyncSession, doc_id: uuid.UUID) -> None:
        result = await db.execute(select(LegalDoc).where(LegalDoc.id == doc_id))
        doc = result.scalar_one_or_none()
        if doc:
            await db.delete(doc)

    async def ingest_background(self, doc_id: uuid.UUID) -> None:
        """Background task: fetch from law API and embed chunks."""
        from app.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(select(LegalDoc).where(LegalDoc.id == doc_id))
                doc = result.scalar_one_or_none()
                if not doc:
                    return

                doc.sync_status = ParseStatus.processing
                await db.flush()

                if not settings.law_api_oc:
                    doc.sync_status = ParseStatus.failed
                    doc.sync_error = (
                        "LAW_API_OC 환경변수가 설정되지 않았습니다. "
                        ".env에 law_api_oc=이메일 추가하세요."
                    )
                    await db.commit()
                    return

                raw_content, meta = await self._fetch_from_api(doc.law_name, doc.law_mst)
                doc.raw_content = raw_content[:50000]  # cap at 50k chars
                doc.law_mst = meta.get("mst", doc.law_mst)
                doc.promulgation_date = meta.get("promulgation_date")
                doc.effective_date = meta.get("effective_date")
                doc.total_articles = meta.get("total_articles")

                chunk_count = await self._chunk_and_embed(db, doc, raw_content)
                doc.total_chunks = chunk_count
                doc.sync_status = ParseStatus.completed
                await db.commit()
                logger.info("legal_doc_synced", law_name=doc.law_name, chunks=chunk_count)

            except Exception as e:
                logger.error("legal_doc_sync_failed", doc_id=str(doc_id), error=str(e))
                try:
                    result = await db.execute(select(LegalDoc).where(LegalDoc.id == doc_id))
                    doc = result.scalar_one_or_none()
                    if doc:
                        doc.sync_status = ParseStatus.failed
                        doc.sync_error = str(e)[:500]
                        await db.commit()
                except Exception:
                    pass

    async def _fetch_from_api(self, law_name: str, law_mst: str | None) -> tuple[str, dict]:
        oc = settings.law_api_oc
        meta: dict[str, Any] = {}

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Search for the law to get MST if not provided
            if not law_mst:
                params = {"OC": oc, "target": "law", "type": "JSON", "query": law_name}
                resp = await client.get(LAW_SEARCH_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
                laws = data.get("LawSearch", {}).get("law", [])
                if not laws:
                    raise ValueError(f"법령을 찾을 수 없습니다: {law_name}")
                if isinstance(laws, dict):
                    laws = [laws]
                best = laws[0]
                law_mst = str(best.get("법령일련번호", ""))
                meta["promulgation_date"] = best.get("공포일자", "")
                meta["effective_date"] = best.get("시행일자", "")

            meta["mst"] = law_mst

            # Step 2: Fetch law content as XML/text
            params = {"OC": oc, "target": "law", "MST": law_mst, "type": "XML"}
            resp = await client.get(LAW_SERVICE_URL, params=params)
            resp.raise_for_status()

            xml_text = resp.text
            articles = self._parse_law_xml(xml_text)
            meta["total_articles"] = len(articles)

            raw_content = "\n\n".join(
                f"[{art['number']}] {art['title']}\n{art['content']}"
                for art in articles
            )
            return raw_content, meta

    def _parse_law_xml(self, xml_text: str) -> list[dict[str, str]]:
        articles = []
        # Parse <조문단위> blocks
        article_blocks = re.findall(r"<조문단위>(.*?)</조문단위>", xml_text, re.DOTALL)
        for block in article_blocks:
            number_match = re.search(r"<조문번호>(.*?)</조문번호>", block)
            title_match = re.search(r"<조문제목>(.*?)</조문제목>", block)
            content_match = re.search(r"<조문내용>(.*?)</조문내용>", block, re.DOTALL)
            if content_match:
                number = number_match.group(1).strip() if number_match else ""
                title = title_match.group(1).strip() if title_match else ""
                content = re.sub(r"<[^>]+>", "", content_match.group(1)).strip()
                if content:
                    articles.append({"number": number, "title": title, "content": content})

        if not articles:
            # Fallback: extract text between tags
            clean = re.sub(r"<[^>]+>", " ", xml_text)
            clean = re.sub(r"\s+", " ", clean).strip()
            if clean:
                articles.append({"number": "", "title": "", "content": clean})

        return articles

    async def _chunk_and_embed(self, db: AsyncSession, doc: LegalDoc, raw_content: str) -> int:
        chunk_size = 800
        chunk_overlap = 100
        chunks_text = self._split_text(raw_content, chunk_size, chunk_overlap)

        stored = 0
        for idx, (chunk_text, article_number, article_title) in enumerate(chunks_text):
            embedding = await self._rag.embed_text(chunk_text)
            chunk = LegalChunk(
                id=uuid.uuid4(),
                doc_id=doc.id,
                article_number=article_number or None,
                article_title=article_title or None,
                section_title=None,
                chunk_text=chunk_text,
                chunk_index=idx,
                embedding=embedding,
            )
            db.add(chunk)
            stored += 1

        await db.flush()
        return stored

    def _split_text(self, text: str, chunk_size: int, overlap: int) -> list[tuple[str, str, str]]:
        results: list[tuple[str, str, str]] = []
        # Split by article markers
        article_pattern = re.compile(
            r"\[(?P<num>[^\]]+)\]\s*(?P<title>[^\n]*)\n(?P<content>.*?)(?=\[|$)",
            re.DOTALL,
        )
        matches = list(article_pattern.finditer(text))

        if matches:
            for m in matches:
                num = m.group("num").strip()
                title = m.group("title").strip()
                content = m.group("content").strip()
                full = f"[{num}] {title}\n{content}"
                if len(full) <= chunk_size:
                    results.append((full, num, title))
                else:
                    # Split long articles
                    for i in range(0, len(full), chunk_size - overlap):
                        part = full[i : i + chunk_size]
                        if part.strip():
                            results.append((part, num, title))
        else:
            # Plain text chunking
            for i in range(0, len(text), chunk_size - overlap):
                part = text[i : i + chunk_size]
                if part.strip():
                    results.append((part, "", ""))

        return results

    async def search_chunks(
        self,
        db: AsyncSession,
        query_embedding: list[float],
        top_k: int = 5,
        doc_ids: list[uuid.UUID] | None = None,
    ) -> list[dict[str, Any]]:
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        where_clause = "WHERE ld.sync_status = 'completed'"
        if doc_ids:
            id_list = ", ".join(f"'{str(did)}'" for did in doc_ids)
            where_clause += f" AND lc.doc_id IN ({id_list})"

        sql = text(
            f"""
            SELECT
                lc.id,
                lc.doc_id,
                ld.law_name,
                lc.article_number,
                lc.article_title,
                lc.section_title,
                lc.chunk_text,
                lc.chunk_index,
                1 - (lc.embedding <=> '{embedding_str}'::vector) AS similarity
            FROM legal_chunks lc
            JOIN legal_docs ld ON ld.id = lc.doc_id
            {where_clause}
            ORDER BY lc.embedding <=> '{embedding_str}'::vector
            LIMIT :top_k
            """
        )

        result = await db.execute(sql, {"top_k": top_k})
        rows = result.fetchall()

        return [
            {
                "chunk_id": str(row.id),
                "doc_id": str(row.doc_id),
                "law_name": row.law_name,
                "article_number": row.article_number,
                "article_title": row.article_title,
                "section_title": row.section_title,
                "chunk_text": row.chunk_text,
                "chunk_index": row.chunk_index,
                "similarity": float(row.similarity),
                "source_type": "legal",
            }
            for row in rows
        ]

    async def keyword_search_chunks(
        self,
        db: AsyncSession,
        queries: list[str],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """pg_trgm based keyword search across legal chunks."""
        if not queries:
            return []

        query_str = queries[0]  # use primary query for trgm
        sql = text(
            """
            SELECT
                lc.id,
                lc.doc_id,
                ld.law_name,
                lc.article_number,
                lc.article_title,
                lc.section_title,
                lc.chunk_text,
                lc.chunk_index,
                similarity(lc.chunk_text, :query) AS sim_score
            FROM legal_chunks lc
            JOIN legal_docs ld ON ld.id = lc.doc_id
            WHERE ld.sync_status = 'completed'
              AND lc.chunk_text % :query
            ORDER BY sim_score DESC
            LIMIT :top_k
            """
        )

        try:
            result = await db.execute(sql, {"query": query_str, "top_k": top_k})
            rows = result.fetchall()
            return [
                {
                    "chunk_id": str(row.id),
                    "doc_id": str(row.doc_id),
                    "law_name": row.law_name,
                    "article_number": row.article_number,
                    "article_title": row.article_title,
                    "section_title": row.section_title,
                    "chunk_text": row.chunk_text,
                    "chunk_index": row.chunk_index,
                    "similarity": float(row.sim_score),
                    "source_type": "legal",
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning("keyword_search_failed", error=str(e))
            return []
