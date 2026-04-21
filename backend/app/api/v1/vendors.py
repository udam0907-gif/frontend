from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.database import get_db
from app.models.vendor import Vendor
from app.schemas.vendor import VendorCreate, VendorRead, VendorUpdate
from app.services.vendor_extractor import extract_vendor_info

router = APIRouter(tags=["업체"])
logger = get_logger(__name__)

_FILE_TYPE_MAP: dict[str, str] = {
    "business_registration": "business_registration_path",
    "bank_copy": "bank_copy_path",
    "quote_template": "quote_template_path",
    "transaction_statement": "transaction_statement_path",
}


def _generate_safe_filename(filename: str) -> str:
    """원본 파일명에서 안전한 파일명 생성 (공백/특수문자 제거)."""
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    return safe or "file"


class VendorExtractResponse(BaseModel):
    vendor_name: str | None
    business_number: str | None
    contact: str | None
    source: str
    confidence: dict


@router.post("/extract", response_model=VendorExtractResponse)
async def extract_vendor_info_from_file(
    file: UploadFile = File(...),
) -> VendorExtractResponse:
    """
    업로드한 파일(견적서, 거래명세서, 사업자등록증, 통장사본)에서
    업체명 / 사업자번호 / 연락처를 자동 추출한다.
    """
    _ALLOWED = {".docx", ".xlsx", ".pdf", ".jpg", ".jpeg", ".png"}
    original_filename = file.filename or "file"
    ext = Path(original_filename).suffix.lower()
    if ext not in _ALLOWED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"허용되지 않는 파일 형식입니다: {ext}. 허용값: {', '.join(sorted(_ALLOWED))}",
        )

    content = await file.read()
    result = extract_vendor_info(original_filename, content)

    return VendorExtractResponse(
        vendor_name=result["vendor_name"],
        business_number=result["business_number"],
        contact=result["contact"],
        source=result["source"],
        confidence=result["confidence"],
    )


@router.get("/", response_model=list[VendorRead])
async def list_vendors(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[Vendor]:
    result = await db.execute(
        select(Vendor)
        .where(Vendor.project_id == project_id)
        .order_by(Vendor.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/", response_model=VendorRead, status_code=status.HTTP_201_CREATED)
async def create_vendor(
    payload: VendorCreate,
    db: AsyncSession = Depends(get_db),
) -> Vendor:
    vendor = Vendor(
        id=uuid.uuid4(),
        project_id=payload.project_id,
        name=payload.name,
        vendor_category=payload.vendor_category,
        business_number=payload.business_number,
        contact=payload.contact,
    )
    db.add(vendor)
    await db.flush()
    await db.refresh(vendor)
    logger.info("vendor_created", vendor_id=str(vendor.id), name=vendor.name)
    return vendor


@router.get("/{vendor_id}", response_model=VendorRead)
async def get_vendor(
    vendor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Vendor:
    return await _get_or_404(vendor_id, db)


@router.patch("/{vendor_id}", response_model=VendorRead)
async def update_vendor(
    vendor_id: uuid.UUID,
    payload: VendorUpdate,
    db: AsyncSession = Depends(get_db),
) -> Vendor:
    vendor = await _get_or_404(vendor_id, db)
    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(vendor, field, value)
    await db.flush()
    await db.refresh(vendor)
    return vendor


@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_vendor(
    vendor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    vendor = await _get_or_404(vendor_id, db)
    await db.delete(vendor)


@router.post("/{vendor_id}/files", response_model=VendorRead)
async def upload_vendor_file(
    vendor_id: uuid.UUID,
    file_type: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> Vendor:
    """
    업체 파일 업로드.
    file_type: business_registration | bank_copy | quote_template | transaction_statement
    """
    if file_type not in _FILE_TYPE_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"지원하지 않는 파일 유형입니다: {file_type}. "
                   f"허용값: {', '.join(_FILE_TYPE_MAP.keys())}",
        )

    vendor = await _get_or_404(vendor_id, db)

    content = await file.read()
    original_filename = file.filename or "file"

    dest_dir = Path(settings.storage_documents_path) / "vendors" / str(vendor_id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _generate_safe_filename(original_filename)
    file_path = str(dest_dir / f"{file_type}_{safe_name}")
    Path(file_path).write_bytes(content)

    field_name = _FILE_TYPE_MAP[file_type]
    setattr(vendor, field_name, file_path)

    await db.flush()
    await db.refresh(vendor)

    logger.info(
        "vendor_file_uploaded",
        vendor_id=str(vendor_id),
        file_type=file_type,
        path=file_path,
    )
    return vendor


async def _get_or_404(vendor_id: uuid.UUID, db: AsyncSession) -> Vendor:
    result = await db.execute(select(Vendor).where(Vendor.id == vendor_id))
    vendor = result.scalar_one_or_none()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"업체 ID {vendor_id}를 찾을 수 없습니다.",
        )
    return vendor
