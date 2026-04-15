from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.core.security import ALLOWED_MANUAL_EXTENSIONS, generate_safe_filename, validate_file_extension
from app.database import get_db
from app.models.enums import ParseStatus
from app.models.rcms import RcmsManual, RcmsQaSession
from app.schemas.rcms import (
    RcmsManualRead,
    RcmsQaRequest,
    RcmsQaResponse,
    RcmsQaSessionRead,
)
from app.services.llm_service import get_llm_service
from app.services.rag_service import RagService

router = APIRouter(tags=["rcms"])
logger = get_logger(__name__)


def get_rag_service() -> RagService:
    return RagService(get_llm_service())


@router.get("/manuals", response_model=list[RcmsManualRead])
async def list_manuals(
    db: AsyncSession = Depends(get_db),
) -> list[RcmsManual]:
    result = await db.execute(
        select(RcmsManual).order_by(RcmsManual.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/manuals", response_model=RcmsManualRead, status_code=status.HTTP_201_CREATED)
async def upload_manual(
    background_tasks: BackgroundTasks,
    display_name: str = Form(...),
    version: str = Form("1.0"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> RcmsManual:
    original_filename = file.filename or "manual"

    if not validate_file_extension(original_filename, ALLOWED_MANUAL_EXTENSIONS):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"허용되지 않는 파일 형식입니다. 허용: {ALLOWED_MANUAL_EXTENSIONS}",
        )

    content = await file.read()
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="매뉴얼 파일 크기는 100MB를 초과할 수 없습니다.",
        )

    manuals_dir = Path(settings.storage_manuals_path)
    manuals_dir.mkdir(parents=True, exist_ok=True)
    safe_name = generate_safe_filename(original_filename)
    file_path = str(manuals_dir / safe_name)
    Path(file_path).write_bytes(content)

    manual = RcmsManual(
        id=uuid.uuid4(),
        filename=safe_name,
        original_filename=original_filename,
        display_name=display_name,
        file_path=file_path,
        file_size=len(content),
        version=version,
        parse_status=ParseStatus.pending,
        metadata_={},
    )
    db.add(manual)
    await db.flush()
    await db.refresh(manual)

    # Trigger async parsing in background
    manual_id = manual.id
    background_tasks.add_task(_parse_manual_background, manual_id, file_path, original_filename)

    logger.info("manual_uploaded", manual_id=str(manual_id), filename=original_filename)
    return manual


@router.get("/manuals/{manual_id}", response_model=RcmsManualRead)
async def get_manual(
    manual_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RcmsManual:
    result = await db.execute(select(RcmsManual).where(RcmsManual.id == manual_id))
    manual = result.scalar_one_or_none()
    if not manual:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="매뉴얼을 찾을 수 없습니다.",
        )
    return manual


@router.delete("/manuals/{manual_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_manual(
    manual_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(RcmsManual).where(RcmsManual.id == manual_id))
    manual = result.scalar_one_or_none()
    if not manual:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="매뉴얼을 찾을 수 없습니다.",
        )
    try:
        Path(manual.file_path).unlink(missing_ok=True)
    except OSError:
        pass
    await db.delete(manual)


@router.post("/qa", response_model=RcmsQaResponse)
async def ask_question(
    payload: RcmsQaRequest,
    db: AsyncSession = Depends(get_db),
    rag_service: RagService = Depends(get_rag_service),
) -> dict:
    result = await rag_service.answer(
        db=db,
        question=payload.question,
        manual_ids=payload.manual_ids,
    )

    answer_status = result.get("answer_status", "not_found_in_uploaded_manuals")

    # Persist Q&A session for audit log
    session = RcmsQaSession(
        id=uuid.uuid4(),
        question=payload.question,
        answer={
            "short_answer": result["short_answer"],
            "detailed_explanation": result["detailed_explanation"],
            "evidence": result["evidence"],
            "found_in_manual": result["found_in_manual"],
            "answer_status": answer_status,
        },
        retrieved_chunks=result.get("retrieved_chunks", []),
        model_version=result["model_version"],
        prompt_version=result["prompt_version"],
        token_usage=result.get("token_usage", {}),
    )
    db.add(session)
    await db.flush()

    logger.info(
        "rcms_qa_answered",
        question_preview=payload.question[:80],
        answer_status=answer_status,
        evidence_count=len(result.get("evidence", [])),
        manual_ids=[str(mid) for mid in (payload.manual_ids or [])],
    )

    return result


@router.get("/qa/history", response_model=list[RcmsQaSessionRead])
async def get_qa_history(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> list[RcmsQaSession]:
    result = await db.execute(
        select(RcmsQaSession)
        .order_by(RcmsQaSession.created_at.desc())
        .limit(min(limit, 100))
    )
    return list(result.scalars().all())


async def _parse_manual_background(
    manual_id: uuid.UUID,
    file_path: str,
    filename: str,
) -> None:
    """Background task: parse manual and generate embeddings."""
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(RcmsManual).where(RcmsManual.id == manual_id))
            manual = result.scalar_one_or_none()
            if not manual:
                return

            manual.parse_status = ParseStatus.processing
            await db.flush()

            rag = RagService(get_llm_service())
            chunk_count = await rag.ingest_manual(
                db=db,
                manual_id=manual_id,
                file_path=file_path,
                filename=filename,
            )

            manual.parse_status = ParseStatus.completed
            manual.total_chunks = chunk_count
            await db.commit()
            logger.info("manual_parse_completed", manual_id=str(manual_id), chunks=chunk_count)

        except Exception as e:
            logger.error("manual_parse_failed", manual_id=str(manual_id), error=str(e))
            try:
                manual.parse_status = ParseStatus.failed
                manual.parse_error = str(e)
                await db.commit()
            except Exception:
                pass
