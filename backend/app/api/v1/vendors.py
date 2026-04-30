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
    project_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[Vendor]:
    stmt = select(Vendor).where(Vendor.project_id == None).order_by(Vendor.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/", response_model=VendorRead, status_code=status.HTTP_201_CREATED)
async def create_vendor(
    payload: VendorCreate,
    db: AsyncSession = Depends(get_db),
) -> Vendor:
    vendor = Vendor(
        id=uuid.uuid4(),
        project_id=payload.project_id,  # None이면 전역 업체
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

    # XLSX/XLS 양식 파일이면 cell_map 분석 후 vendor_template_pool upsert
    # 등록 시점에만 Claude API 호출 — 출력 시점에는 저장된 cell_map 사용
    if file_type in ("quote_template", "transaction_statement"):
        _ext = Path(file_path).suffix.lower()
        if _ext in (".xlsx", ".xls") and vendor.business_number:
            try:
                from app.models.vendor_pool import VendorTemplatePool
                from app.services.llm_service import get_llm_service
                from app.services.xlsx_cell_mapper import XlsxCellMapper

                _mapper = XlsxCellMapper(get_llm_service())
                _remap = await _mapper.analyze(file_path)
                _cell_map = _remap.get("cell_map", {})

                if _cell_map:
                    _pool_res = await db.execute(
                        select(VendorTemplatePool).where(
                            VendorTemplatePool.vendor_business_number == vendor.business_number
                        )
                    )
                    _pool = _pool_res.scalar_one_or_none()
                    if _pool:
                        _pool.cell_map = _cell_map
                        _pool.field_map = {
                            **_pool.field_map,
                            "_cell_map": _cell_map,
                            "_mapping_status": "auto_mapped",
                        }
                    else:
                        _pool = VendorTemplatePool(
                            id=uuid.uuid4(),
                            vendor_business_number=vendor.business_number,
                            vendor_name=vendor.name,
                            file_format=_ext.lstrip("."),
                            layout_map={},
                            render_profile={},
                            field_map={
                                "_cell_map": _cell_map,
                                "_mapping_status": "auto_mapped",
                            },
                            cell_map=_cell_map,
                            sample_file_path=file_path,
                        )
                        db.add(_pool)
                    await db.flush()
                    logger.info(
                        "vendor_file_cell_map_saved",
                        vendor_id=str(vendor_id),
                        file_type=file_type,
                        cell_count=len(_cell_map),
                    )
            except Exception as _e:
                logger.warning(
                    "vendor_file_cell_map_failed",
                    vendor_id=str(vendor_id),
                    error=str(_e),
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
