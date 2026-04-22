from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.database import get_db
from app.models.company_setting import CompanySetting
from app.schemas.company_setting import CompanySettingRead, CompanySettingUpsert

router = APIRouter(tags=["company-settings"])
logger = get_logger(__name__)

_FILE_TYPE_MAP: dict[str, str] = {
    "business_registration": "company_business_registration_path",
    "bank_copy": "company_bank_copy_path",
    "quote_template": "company_quote_template_path",
    "transaction_statement_template": "company_transaction_statement_template_path",
    "seal_image": "seal_image_path",
}

_ALLOWED_EXTENSIONS: dict[str, set[str]] = {
    "business_registration": {".pdf", ".jpg", ".jpeg", ".png"},
    "bank_copy": {".pdf", ".jpg", ".jpeg", ".png"},
    "quote_template": {".docx"},
    "transaction_statement_template": {".docx"},
    "seal_image": {".jpg", ".jpeg", ".png"},
}


def _generate_safe_filename(filename: str) -> str:
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    return safe or "file"


async def _get_company_setting(company_id: str, db: AsyncSession) -> CompanySetting | None:
    result = await db.execute(
        select(CompanySetting).where(CompanySetting.company_id == company_id)
    )
    return result.scalar_one_or_none()


async def _get_or_create_company_setting(company_id: str, db: AsyncSession) -> CompanySetting:
    company_setting = await _get_company_setting(company_id, db)
    if company_setting:
        return company_setting

    company_setting = CompanySetting(id=uuid.uuid4(), company_id=company_id)
    db.add(company_setting)
    await db.flush()
    await db.refresh(company_setting)
    return company_setting


@router.get("/", response_model=CompanySettingRead)
async def get_company_settings(
    company_id: str = "default",
    db: AsyncSession = Depends(get_db),
) -> CompanySettingRead:
    company_setting = await _get_company_setting(company_id, db)
    if not company_setting:
        return CompanySettingRead(company_id=company_id)
    return company_setting


@router.put("/", response_model=CompanySettingRead)
async def upsert_company_settings(
    payload: CompanySettingUpsert,
    db: AsyncSession = Depends(get_db),
) -> CompanySetting:
    company_setting = await _get_or_create_company_setting(payload.company_id, db)
    for field, value in payload.model_dump().items():
        if field == "company_id":
            continue
        setattr(company_setting, field, value)
    await db.flush()
    await db.refresh(company_setting)
    logger.info("company_settings_upserted", company_id=payload.company_id)
    return company_setting


@router.post("/files", response_model=CompanySettingRead)
async def upload_company_file(
    file_type: str = Form(...),
    file: UploadFile = File(...),
    company_id: str = Form("default"),
    db: AsyncSession = Depends(get_db),
) -> CompanySetting:
    if file_type not in _FILE_TYPE_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"지원하지 않는 파일 유형입니다: {file_type}",
        )

    ext = Path(file.filename or "file").suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS[file_type]:
        allowed = ", ".join(sorted(_ALLOWED_EXTENSIONS[file_type]))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"허용되지 않는 파일 형식입니다: {ext}. 허용값: {allowed}",
        )

    company_setting = await _get_or_create_company_setting(company_id, db)
    content = await file.read()
    safe_name = _generate_safe_filename(file.filename or "file")

    dest_dir = Path(settings.storage_documents_path) / "company_settings" / company_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    file_path = str(dest_dir / f"{file_type}_{safe_name}")
    Path(file_path).write_bytes(content)

    setattr(company_setting, _FILE_TYPE_MAP[file_type], file_path)
    await db.flush()
    await db.refresh(company_setting)

    logger.info("company_file_uploaded", company_id=company_id, file_type=file_type, path=file_path)
    return company_setting
