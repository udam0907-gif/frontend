from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database import get_db
from app.models.legal import LegalDoc
from app.schemas.legal import (
    LegalDocRead,
    LegalSyncDefaultsResponse,
    LegalSyncRequest,
    LegalSyncResponse,
)
from app.services.legal_rag_service import DEFAULT_LAWS, LegalRagService
from app.services.llm_service import get_llm_service
from app.services.rag_service import RagService

router = APIRouter(tags=["legal"])
logger = get_logger(__name__)


def get_legal_rag_service() -> LegalRagService:
    rag = RagService(get_llm_service())
    return LegalRagService(rag)


@router.get("/laws", response_model=list[LegalDocRead])
async def list_laws(db: AsyncSession = Depends(get_db)) -> list[LegalDoc]:
    svc = get_legal_rag_service()
    return await svc.list_docs(db)


@router.post("/laws/sync", response_model=LegalSyncResponse)
async def sync_law(
    payload: LegalSyncRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = get_legal_rag_service()
    doc = await svc.sync_law(db, payload.law_name, payload.law_mst)
    background_tasks.add_task(svc.ingest_background, doc.id)
    logger.info("legal_sync_started", law_name=payload.law_name, doc_id=str(doc.id))
    return {"message": f"'{payload.law_name}' 동기화를 시작했습니다.", "law_name": payload.law_name}


@router.post("/laws/sync-defaults", response_model=LegalSyncDefaultsResponse)
async def sync_default_laws(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = get_legal_rag_service()
    docs = await svc.sync_defaults(db)
    for doc in docs:
        background_tasks.add_task(svc.ingest_background, doc.id)
    logger.info("legal_sync_defaults_started", count=len(docs))
    return {
        "message": f"기본 법령 {len(docs)}개 동기화를 시작했습니다.",
        "laws": DEFAULT_LAWS,
    }


@router.delete("/laws/{doc_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_law(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(LegalDoc).where(LegalDoc.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="법령 자료를 찾을 수 없습니다.",
        )
    await db.delete(doc)
