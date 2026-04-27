from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.database import get_db
from app.models.company_setting import CompanySetting
from app.schemas.company_setting import (
    CompanySettingExtractResponse,
    CompanySettingExtractedFields,
    CompanySettingFileStatus,
    CompanySettingRead,
    CompanySettingUpsert,
)
from app.services.company_setting_extractor import extract_company_setting_info

router = APIRouter(tags=["company-settings"])
logger = get_logger(__name__)

_FILE_TYPE_MAP: dict[str, str] = {
    "business_registration": "company_business_registration_path",
    "bank_copy": "company_bank_copy_path",
    "quote_template": "company_quote_template_path",
    "transaction_statement_template": "company_transaction_statement_template_path",
    "seal_image": "seal_image_path",
}

_STATUS_FIELD_MAP: dict[str, str] = {
    "business_registration": "company_business_registration_path",
    "bank_copy": "company_bank_copy_path",
    "quote_template": "company_quote_template_path",
    "transaction_statement_template": "company_transaction_statement_template_path",
    "seal_image": "seal_image_path",
}

_ALLOWED_EXTENSIONS: dict[str, set[str]] = {
    "business_registration": {".pdf", ".jpg", ".jpeg", ".png"},
    "bank_copy": {".pdf", ".jpg", ".jpeg", ".png"},
    "quote_template": {".docx", ".xlsx", ".xls", ".pdf"},
    "transaction_statement_template": {".docx", ".xlsx", ".xls", ".pdf"},
    "seal_image": {".jpg", ".jpeg", ".png"},
}


def _generate_safe_filename(filename: str) -> str:
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    return safe or "file"


def _resolve_storage_path(raw_path: str | None) -> Path | None:
    if not raw_path:
        return None
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return Path("/app") / raw_path


def _serialize_company_setting(company_setting: CompanySetting) -> CompanySettingRead:
    file_statuses: dict[str, CompanySettingFileStatus] = {}

    for file_type, field_name in _STATUS_FIELD_MAP.items():
        raw_path = getattr(company_setting, field_name, None)
        resolved_path = _resolve_storage_path(raw_path)
        exists = bool(resolved_path and resolved_path.exists() and resolved_path.is_file())
        updated_at = None
        if exists and resolved_path is not None:
            updated_at = datetime.fromtimestamp(resolved_path.stat().st_mtime)

        file_statuses[file_type] = CompanySettingFileStatus(
            path=raw_path,
            exists=exists,
            file_name=resolved_path.name if exists and resolved_path is not None else None,
            updated_at=updated_at,
        )

    return CompanySettingRead(
        id=company_setting.id,
        company_id=company_setting.company_id,
        company_name=company_setting.company_name,
        company_registration_number=company_setting.company_registration_number,
        representative_name=company_setting.representative_name,
        address=company_setting.address,
        business_type=company_setting.business_type,
        business_item=company_setting.business_item,
        phone=company_setting.phone,
        fax=company_setting.fax,
        email=company_setting.email,
        seal_image_path=company_setting.seal_image_path,
        company_business_registration_path=company_setting.company_business_registration_path,
        company_bank_copy_path=company_setting.company_bank_copy_path,
        company_quote_template_path=company_setting.company_quote_template_path,
        company_transaction_statement_template_path=company_setting.company_transaction_statement_template_path,
        file_statuses=file_statuses,
        created_at=company_setting.created_at,
        updated_at=company_setting.updated_at,
    )


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
    return _serialize_company_setting(company_setting)


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
    return _serialize_company_setting(company_setting)


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
    return _serialize_company_setting(company_setting)


@router.delete("/files", response_model=CompanySettingRead)
async def delete_company_file(
    company_id: str = Query("default"),
    file_type: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> CompanySettingRead:
    if file_type not in _FILE_TYPE_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"지원하지 않는 파일 유형입니다: {file_type}",
        )

    company_setting = await _get_or_create_company_setting(company_id, db)
    field_name = _FILE_TYPE_MAP[file_type]
    raw_path = getattr(company_setting, field_name, None)
    resolved_path = _resolve_storage_path(raw_path)

    if resolved_path and resolved_path.exists() and resolved_path.is_file():
        resolved_path.unlink()

    setattr(company_setting, field_name, None)

    # 파일 삭제 시 해당 소스에서 추출된 필드도 함께 초기화
    _FILE_TYPE_OWNED_FIELDS: dict[str, list[str]] = {
        "business_registration": [
            "company_name", "company_registration_number", "representative_name",
            "address", "business_type", "business_item",
        ],
        "quote_template": ["phone", "fax", "email"],
        "transaction_statement_template": ["phone", "fax", "email"],
        "bank_copy": [],
        "seal_image": [],
    }
    for field in _FILE_TYPE_OWNED_FIELDS.get(file_type, []):
        setattr(company_setting, field, None)

    company_setting.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(company_setting)

    logger.info("company_file_deleted", company_id=company_id, file_type=file_type, path=raw_path)
    return _serialize_company_setting(company_setting)


@router.post("/extract", response_model=CompanySettingExtractResponse)
async def extract_company_settings_from_files(
    company_id: str = "default",
    file_type: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> CompanySettingExtractResponse:
    company_setting = await _get_company_setting(company_id, db)
    if not company_setting:
        return CompanySettingExtractResponse(
            company_id=company_id,
            extracted=CompanySettingExtractedFields(),
            source_by_field={},
            used_files=[],
        )

    preferred_sources: tuple[str, ...] | None = None
    if file_type:
        if file_type not in _FILE_TYPE_MAP:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"지원하지 않는 파일 유형입니다: {file_type}",
            )
        preferred_sources = (file_type,)

    result = extract_company_setting_info(
        company_setting,
        preferred_sources=preferred_sources,
    )

    # 추출된 필드를 company_settings 테이블에 저장
    extracted = result["extracted"]
    fields_to_clear: list[str] = result.get("fields_to_clear", [])

    update_fields: dict[str, str] = {}
    for field in (
        "company_name",
        "company_registration_number",
        "representative_name",
        "address",
        "business_type",
        "business_item",
        "phone",
        "fax",
        "email",
    ):
        value = extracted.get(field)
        if value and isinstance(value, str) and value.strip():
            update_fields[field] = value.strip()

    needs_save = bool(update_fields) or bool(fields_to_clear)
    if needs_save:
        # 추출된 값 저장
        for key, value in update_fields.items():
            setattr(company_setting, key, value)
        # 이전 소스 잔재 필드 클리어 (예: 견적서 전화번호 → 사업자등록증 재업로드 시 삭제)
        for field in fields_to_clear:
            if field not in update_fields:  # 이번에 새로 추출된 값은 덮어쓰지 않음
                setattr(company_setting, field, None)
        company_setting.updated_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(company_setting)
        logger.info(
            "company_setting_extracted_and_saved",
            company_id=company_id,
            saved_fields=list(update_fields.keys()),
            cleared_fields=fields_to_clear,
        )

    return CompanySettingExtractResponse(
        company_id=company_id,
        extracted=CompanySettingExtractedFields(**result["extracted"]),
        source_by_field=result["source_by_field"],
        used_files=result["used_files"],
    )
