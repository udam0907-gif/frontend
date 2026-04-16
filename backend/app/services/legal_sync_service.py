"""
Korea Law Open API (국가법령정보 오픈 API) integration.

Registration:  https://www.law.go.kr/LSW/openApi.do
API docs:      https://www.law.go.kr/LSW/openApiIntro.do

Endpoints used
--------------
Law search  : GET https://www.law.go.kr/DRF/lawSearch.do
                ?OC={oc}&target=law&type=XML&display=5&query={name}

Law content : GET https://www.law.go.kr/DRF/lawService.do
                ?OC={oc}&target=law&MST={mst}&type=XML

AdminRule search : GET https://www.law.go.kr/DRF/lawSearch.do
                     ?OC={oc}&target=admrul&type=XML&display=5&query={name}

AdminRule content: GET https://www.law.go.kr/DRF/lawService.do
                     ?OC={oc}&target=admrul&ID={id}&type=XML
"""
from __future__ import annotations

import re
import uuid
import xml.etree.ElementTree as ET
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import AppError, NotFoundError
from app.core.logging import get_logger
from app.models.enums import ParseStatus

logger = get_logger(__name__)

# ─── Default laws to sync ────────────────────────────────────────────────────
# target: "law" for formal laws/decrees, "admrul" for ministerial notifications (고시)
DEFAULT_LAWS: list[dict[str, str]] = [
    {
        "name": "국가연구개발혁신법",
        "query": "국가연구개발혁신법",
        "target": "law",
    },
    {
        "name": "국가연구개발혁신법 시행령",
        "query": "국가연구개발혁신법 시행령",
        "target": "law",
    },
    {
        "name": "국가연구개발사업 연구개발비 사용 기준",
        "query": "연구개발비 사용 기준",
        "target": "admrul",
    },
]

# Characters per chunk when splitting long articles
_ARTICLE_CHUNK_SIZE = 800
_ARTICLE_CHUNK_OVERLAP = 80


class LegalSyncService:
    """
    Fetches Korean legal documents from the Korea Law Open API,
    parses them into article-level chunks, generates embeddings,
    and stores them in the legal_documents / legal_chunks tables.
    """

    def __init__(self, rag_service: Any) -> None:
        # RagService injected to reuse embed_text()
        self._rag = rag_service

    # ─── Public API ──────────────────────────────────────────────────────────

    async def sync_law_by_name(
        self,
        db: AsyncSession,
        law_name: str,
        law_mst: str | None = None,
        api_target: str = "law",
    ) -> str:
        """
        Sync a single law by name (with optional MST hint).
        api_target: "law" for 법령/시행령, "admrul" for 행정규칙(고시)
        Returns the LegalDocument.id (str) after committing.
        """
        from app.models.legal import LegalDocument, LegalChunk

        oc = settings.law_api_oc
        if not oc:
            raise AppError(
                "Korea Law API OC(이메일)이 설정되지 않았습니다. "
                ".env에 LAW_API_OC=<등록된 이메일> 을 추가하세요."
            )

        # Find or create document record
        from sqlalchemy import select
        result = await db.execute(
            select(LegalDocument).where(LegalDocument.law_name == law_name)
        )
        doc = result.scalar_one_or_none()

        if doc is None:
            doc = LegalDocument(
                id=uuid.uuid4(),
                law_name=law_name,
                law_mst=law_mst or "",
                source_type="api",
                sync_status=ParseStatus.pending,
            )
            db.add(doc)
            await db.flush()

        doc.sync_status = ParseStatus.processing
        doc.sync_error = None
        await db.flush()
        doc_id = doc.id

        try:
            # 1. Resolve MST/ID code
            if not law_mst:
                law_mst = await self._search_mst(oc, law_name, api_target)
                if not law_mst:
                    raise NotFoundError(f"법령을 찾을 수 없습니다: {law_name}")

            # 2. Fetch full XML
            xml_content = await self._fetch_law_xml(oc, law_mst, api_target)

            # 3. Parse articles
            articles = self._parse_articles(xml_content, api_target)

            # 4. Update document metadata
            from sqlalchemy import select as sel
            res = await db.execute(sel(LegalDocument).where(LegalDocument.id == doc_id))
            doc = res.scalar_one()
            doc.law_mst = law_mst

            # Try to extract dates from XML
            meta = self._parse_meta(xml_content)
            doc.promulgation_date = meta.get("promulgation_date")
            doc.effective_date = meta.get("effective_date")
            doc.total_articles = len(articles)

            # 5. Delete old chunks
            from sqlalchemy import delete as del_
            await db.execute(del_(LegalChunk).where(LegalChunk.document_id == doc_id))

            # 6. Embed & store chunks
            stored = 0
            for chunk_data in self._articles_to_chunks(articles):
                embed_text = chunk_data["chunk_text"][:1500]
                embedding = await self._rag.embed_text(embed_text)
                db.add(LegalChunk(
                    id=uuid.uuid4(),
                    document_id=doc_id,
                    article_number=chunk_data.get("article_number"),
                    article_title=chunk_data.get("article_title"),
                    chunk_text=chunk_data["chunk_text"],
                    chunk_index=chunk_data["chunk_index"],
                    embedding=embedding,
                ))
                stored += 1

            doc.total_chunks = stored
            doc.sync_status = ParseStatus.completed
            await db.commit()

            logger.info(
                "legal_sync_completed",
                law_name=law_name,
                law_mst=law_mst,
                articles=len(articles),
                chunks=stored,
            )
            return str(doc_id)

        except AppError:
            await db.rollback()
            # Re-fetch and mark failed
            async with db.begin():
                from sqlalchemy import select as sel2
                res2 = await db.execute(sel2(LegalDocument).where(LegalDocument.id == doc_id))
                doc2 = res2.scalar_one_or_none()
                if doc2:
                    doc2.sync_status = ParseStatus.failed
                    doc2.sync_error = f"법령을 찾을 수 없거나 API 오류"
            raise
        except Exception as exc:
            logger.error("legal_sync_failed", law_name=law_name, error=str(exc))
            try:
                await db.rollback()
                async with db.begin():
                    from sqlalchemy import select as sel3
                    res3 = await db.execute(sel3(LegalDocument).where(LegalDocument.id == doc_id))
                    doc3 = res3.scalar_one_or_none()
                    if doc3:
                        doc3.sync_status = ParseStatus.failed
                        doc3.sync_error = str(exc)[:500]
            except Exception:
                pass
            raise AppError(f"법령 동기화 실패: {exc}") from exc

    # ─── Korea Law Open API calls ─────────────────────────────────────────────

    async def _search_mst(
        self, oc: str, law_name: str, api_target: str = "law"
    ) -> str | None:
        """Search for a law/admrul and return its MST/ID code."""
        url = f"{settings.law_api_base_url}/lawSearch.do"
        section = "admRulNm" if api_target == "admrul" else "lawNm"
        params = {
            "OC": oc,
            "target": api_target,
            "type": "XML",
            "display": "5",
            "query": law_name,
            "section": section,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
            if api_target == "admrul":
                return self._extract_admrul_id(resp.text, law_name)
            return self._extract_mst(resp.text, law_name)
        except httpx.HTTPError as e:
            logger.error("law_search_http_error", url=url, error=str(e))
            raise AppError(f"법령 검색 API 오류: {e}") from e

    async def _fetch_law_xml(
        self, oc: str, mst: str, api_target: str = "law"
    ) -> str:
        """Fetch the full law/admrul XML by MST/ID code."""
        url = f"{settings.law_api_base_url}/lawService.do"
        if api_target == "admrul":
            params = {
                "OC": oc,
                "target": "admrul",
                "ID": mst,
                "type": "XML",
            }
        else:
            params = {
                "OC": oc,
                "target": "law",
                "MST": mst,
                "type": "XML",
            }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
            return resp.text
        except httpx.HTTPError as e:
            logger.error("law_fetch_http_error", mst=mst, error=str(e))
            raise AppError(f"법령 원문 API 오류: {e}") from e

    # ─── XML parsing ─────────────────────────────────────────────────────────

    def _extract_mst(self, xml_text: str, target_name: str) -> str | None:
        """
        Parse law search results XML and return the 법령일련번호 (MST) of the best match.

        Actual API structure:
        <LawSearch>
          <law id="1">
            <법령일련번호>260807</법령일련번호>
            <법령명한글><![CDATA[국가연구개발혁신법]]></법령명한글>
          </law>
        </LawSearch>
        """
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            logger.warning("law_search_xml_parse_error", snippet=xml_text[:200])
            return None

        best_mst: str | None = None

        for item in root.findall(".//law"):
            name_el = item.find("법령명한글")
            mst_el  = item.find("법령일련번호")
            if mst_el is None or not mst_el.text:
                continue
            mst_val = mst_el.text.strip()
            if name_el is not None:
                name_text = (name_el.text or "").strip()
                if name_text == target_name:
                    return mst_val  # exact match
                if target_name in name_text or name_text in target_name:
                    best_mst = mst_val
            if best_mst is None:
                best_mst = mst_val  # fallback to first result

        if best_mst:
            return best_mst

        # Regex fallback
        m = re.search(r"<법령일련번호>(\d+)</법령일련번호>", xml_text)
        return m.group(1) if m else None

    def _extract_admrul_id(self, xml_text: str, target_name: str) -> str | None:
        """
        Parse administrative rule search results XML and return 행정규칙일련번호.

        Actual API structure:
        <AdmRulSearch>
          <admrul id="1">
            <행정규칙일련번호>2100000275762</행정규칙일련번호>
            <행정규칙명><![CDATA[국가연구개발사업 연구개발비 사용 기준]]></행정규칙명>
          </admrul>
        </AdmRulSearch>
        """
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            logger.warning("admrul_search_xml_parse_error", snippet=xml_text[:200])
            return None

        best_id: str | None = None

        for item in root.findall(".//admrul"):
            name_el = item.find("행정규칙명")
            id_el   = item.find("행정규칙일련번호")
            if id_el is None or not id_el.text:
                continue
            id_val = id_el.text.strip()
            if name_el is not None:
                name_text = (name_el.text or "").strip()
                if name_text == target_name:
                    return id_val  # exact match
                if target_name in name_text or name_text in target_name:
                    best_id = id_val
            if best_id is None:
                best_id = id_val  # fallback to first result

        if best_id:
            return best_id

        # Regex fallback
        m = re.search(r"<행정규칙일련번호>(\d+)</행정규칙일련번호>", xml_text)
        return m.group(1) if m else None

    def _parse_meta(self, xml_text: str) -> dict[str, str | None]:
        """Extract metadata (dates) from law or admrul XML."""
        meta: dict[str, str | None] = {
            "promulgation_date": None,
            "effective_date": None,
        }
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return meta

        for tag, key in [
            ("공포일자", "promulgation_date"),
            ("발령일자", "promulgation_date"),   # admrul uses 발령일자
            ("시행일자", "effective_date"),
        ]:
            el = root.find(f".//{tag}")
            if el is not None and el.text and not meta.get(key):
                meta[key] = el.text.strip()
        return meta

    def _parse_articles(
        self, xml_text: str, api_target: str = "law"
    ) -> list[dict[str, str]]:
        """
        Parse law/admrul XML into a list of articles.

        For law (target=law):
          Uses <조문단위> / <조문번호> / <조문제목> / <조문내용> structure.

        For admrul (target=admrul):
          Uses flat <조문내용> CDATA sections at the root level.
          Each section contains "제N조(title) text..." format.
        """
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.warning("law_xml_parse_error", error=str(e))
            return self._fallback_parse(xml_text)

        if api_target == "admrul":
            return self._parse_admrul_articles(root, xml_text)

        articles: list[dict[str, str]] = []

        # Korea Law API formal law structure:
        # <조문단위 조문키="...">
        #   <조문번호>1</조문번호>
        #   <조문제목>목적</조문제목>
        #   <조문내용>제1조(목적)...</조문내용>
        #   <항><호><호내용>...</호내용></호></항>
        # </조문단위>
        for unit in root.iter("조문단위"):
            # Skip 전문(preamble) entries that only contain chapter headers
            is_jomun = self._text_of(unit, ["조문여부"])
            if is_jomun == "전문":
                continue

            raw_num = self._text_of(unit, ["조문번호"])
            article_title = self._text_of(unit, ["조문제목"])
            article_num = f"제{raw_num}조" if raw_num else ""

            parts: list[str] = []

            content = self._text_of(unit, ["조문내용"])
            if content:
                parts.append(content.strip())

            for para in unit.findall(".//항"):
                for ho in para.findall(".//호"):
                    ho_text = self._text_of(ho, ["호내용"])
                    if ho_text:
                        parts.append(ho_text.strip())

            body = "\n".join(p for p in parts if p).strip()
            if body:
                articles.append({
                    "article_number": article_num,
                    "article_title": article_title,
                    "text": body,
                })

        if not articles:
            return self._fallback_parse(xml_text)

        logger.info("law_articles_parsed", count=len(articles))
        return articles

    def _parse_admrul_articles(
        self, root: ET.Element, xml_text: str
    ) -> list[dict[str, str]]:
        """
        Parse administrative rule (고시) XML.

        Structure: <AdmRulService> with multiple flat <조문내용> CDATA entries.
        Each entry may be a chapter header ("제N장 ...") or an article ("제N조(title) text").
        """
        articles: list[dict[str, str]] = []

        # Collect all <조문내용> elements (both direct and nested)
        content_els = root.findall(".//조문내용")
        if not content_els:
            return self._fallback_parse(xml_text)

        # Regex to detect article start: 제N조 or 제N조의N
        article_re = re.compile(r"^(제\d+조(?:의\d+)?)\s*(?:\(([^)]+)\))?\s*")
        # Chapter/section headers to skip
        chapter_re = re.compile(r"^제\d+[장절편관]\s")

        for el in content_els:
            text = (el.text or "").strip()
            if not text:
                continue

            # Skip pure chapter/section headers
            if chapter_re.match(text) and len(text) < 30:
                continue

            m = article_re.match(text)
            if m:
                article_num = m.group(1)      # e.g. "제1조"
                article_title = m.group(2) or ""  # e.g. "목적"
            else:
                article_num = ""
                article_title = ""

            articles.append({
                "article_number": article_num,
                "article_title": article_title,
                "text": text,
            })

        if not articles:
            return self._fallback_parse(xml_text)

        logger.info("admrul_articles_parsed", count=len(articles))
        return articles

    def _text_of(self, el: ET.Element, tags: list[str]) -> str:
        """Find first matching child tag and return its stripped text."""
        for tag in tags:
            child = el.find(tag)
            if child is not None and child.text:
                return child.text.strip()
        return ""

    def _fallback_parse(self, xml_text: str) -> list[dict[str, str]]:
        """
        If structured parsing fails, extract all text content and
        split it into 800-char pseudo-articles.
        """
        # Strip XML tags
        clean = re.sub(r"<[^>]+>", " ", xml_text)
        clean = re.sub(r"\s+", " ", clean).strip()

        if not clean:
            return []

        chunks = []
        step = _ARTICLE_CHUNK_SIZE - _ARTICLE_CHUNK_OVERLAP
        for i, start in enumerate(range(0, len(clean), step)):
            text = clean[start:start + _ARTICLE_CHUNK_SIZE].strip()
            if text:
                chunks.append({"article_number": "", "article_title": "", "text": text})

        return chunks

    # ─── Chunking ─────────────────────────────────────────────────────────────

    def _articles_to_chunks(
        self,
        articles: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """
        Convert articles into retrieval chunks.
        Short articles = 1 chunk each.
        Long articles are split with overlap.
        """
        chunks: list[dict[str, Any]] = []
        chunk_idx = 0

        for article in articles:
            text = article["text"]
            article_num = article.get("article_number", "")
            article_title = article.get("article_title", "")

            if len(text) <= _ARTICLE_CHUNK_SIZE:
                chunks.append({
                    "article_number": article_num,
                    "article_title": article_title,
                    "chunk_text": text,
                    "chunk_index": chunk_idx,
                })
                chunk_idx += 1
            else:
                # Split long article
                start = 0
                while start < len(text):
                    end = min(start + _ARTICLE_CHUNK_SIZE, len(text))
                    chunk_text = text[start:end].strip()
                    if chunk_text:
                        suffix = "" if start == 0 else " (계속)"
                        chunks.append({
                            "article_number": article_num + suffix,
                            "article_title": article_title,
                            "chunk_text": chunk_text,
                            "chunk_index": chunk_idx,
                        })
                        chunk_idx += 1
                    if end >= len(text):
                        break
                    start = end - _ARTICLE_CHUNK_OVERLAP

        return chunks

    # ─── Background sync helper ────────────────────────────────────────────────

    @staticmethod
    async def sync_law_background(
        law_name: str,
        law_mst: str | None = None,
        api_target: str = "law",
    ) -> None:
        """
        Run full law sync inside its own DB session (for use as a background task).
        Imports are deferred to avoid circular imports at module load time.
        """
        from app.database import AsyncSessionLocal
        from app.services.llm_service import get_llm_service
        from app.services.rag_service import RagService

        async with AsyncSessionLocal() as db:
            rag = RagService(get_llm_service())
            svc = LegalSyncService(rag)
            await svc.sync_law_by_name(db, law_name, law_mst, api_target)
