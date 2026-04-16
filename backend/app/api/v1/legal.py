"""
Legal document management endpoints.

Mounted under /api/v1/rcms/laws by main.py.
Allows administrators to:
  - List ingested legal documents
  - Trigger sync from Korea Law Open API
  - Delete a legal document (and its chunks)
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database import get_db
from app.models.legal import LegalDocument
from app.schemas.rcms import LegalDocRead, LegalSyncRequest
from app.services.legal_sync_service import DEFAULT_LAWS, LegalSyncService

router = APIRouter(tags=["법령 관리"])
logger = get_logger(__name__)


def _get_sync_service() -> LegalSyncService:
    """
    Returns a LegalSyncService that borrows embed_text() from a transient RagService.
    The RagService only needs the LLM for Q&A, not for embedding — so this is safe.
    """
    from app.services.llm_service import get_llm_service
    from app.services.rag_service import RagService
    rag = RagService(get_llm_service())
    return LegalSyncService(rag)


@router.get("", response_model=list[LegalDocRead])
async def list_legal_docs(
    db: AsyncSession = Depends(get_db),
) -> list[LegalDocument]:
    """List all ingested legal documents."""
    result = await db.execute(
        select(LegalDocument).order_by(LegalDocument.created_at.asc())
    )
    return list(result.scalars().all())


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_law(
    payload: LegalSyncRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Trigger async sync of a single law from Korea Law Open API.
    The sync runs in the background; poll GET /laws to check status.
    """
    # Check for duplicate in-progress sync
    result = await db.execute(
        select(LegalDocument).where(LegalDocument.law_name == payload.law_name)
    )
    existing = result.scalar_one_or_none()
    if existing and existing.sync_status.value == "processing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 동기화 중입니다: {payload.law_name}",
        )

    # Auto-detect api_target from DEFAULT_LAWS if not provided explicitly
    api_target = payload.api_target or "law"
    for law in DEFAULT_LAWS:
        if law["name"] == payload.law_name:
            api_target = law.get("target", "law")
            break

    background_tasks.add_task(
        LegalSyncService.sync_law_background,
        payload.law_name,
        payload.law_mst,
        api_target,
    )
    logger.info("legal_sync_triggered", law_name=payload.law_name)
    return {"message": f"법령 동기화를 시작했습니다: {payload.law_name}", "law_name": payload.law_name}


@router.post("/sync-defaults", status_code=status.HTTP_202_ACCEPTED)
async def sync_default_laws(background_tasks: BackgroundTasks) -> dict:
    """
    Trigger async sync for all 3 default R&D laws:
    - 국가연구개발혁신법
    - 국가연구개발혁신법 시행령
    - 국가연구개발사업 연구개발비 사용 기준
    """
    names = []
    for law in DEFAULT_LAWS:
        background_tasks.add_task(
            LegalSyncService.sync_law_background,
            law["name"],
            None,
            law.get("target", "law"),
        )
        names.append(law["name"])

    logger.info("legal_sync_defaults_triggered", laws=names)
    return {"message": f"{len(names)}개 법령 동기화를 시작했습니다.", "laws": names}


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_legal_doc(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a legal document and all its chunks."""
    result = await db.execute(
        select(LegalDocument).where(LegalDocument.id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="법령 문서를 찾을 수 없습니다.",
        )
    await db.delete(doc)
    logger.info("legal_doc_deleted", doc_id=str(doc_id), law_name=doc.law_name)
