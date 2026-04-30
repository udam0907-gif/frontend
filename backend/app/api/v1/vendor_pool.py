from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.core.security import ALLOWED_TEMPLATE_EXTENSIONS, generate_safe_filename, validate_file_extension
from app.database import get_db
from app.models.vendor_pool import VendorTemplatePool
from app.services.llm_service import get_llm_service
from app.services.vendor_template_analyzer import VendorTemplateAnalyzer
from app.services.xlsx_cell_mapper import XlsxCellMapper

router = APIRouter(tags=["vendor-pool"])
logger = get_logger(__name__)
_analyzer = VendorTemplateAnalyzer()


@router.post("/analyze", status_code=status.HTTP_201_CREATED)
async def analyze_vendor_template(
    company_id: uuid.UUID = Form(...),
    vendor_name: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    업체 템플릿 파일 업로드 → 분석 → 공유 풀 등록.
    같은 사업자번호가 풀에 있으면 재사용 (분석 재호출 없음).
    """
    original_filename = file.filename or "template"
    if not validate_file_extension(original_filename, ALLOWED_TEMPLATE_EXTENSIONS):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"허용 형식: {ALLOWED_TEMPLATE_EXTENSIONS}",
        )

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="파일 크기 20MB 초과")

    dest_dir = Path(settings.storage_templates_path) / "vendor_pool"
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = generate_safe_filename(original_filename)
    file_path = str(dest_dir / safe_name)
    Path(file_path).write_bytes(content)

    result = await _analyzer.analyze_and_register(
        db=db,
        file_path=file_path,
        filename=original_filename,
        vendor_name=vendor_name,
        company_id=company_id,
    )

    logger.info(
        "vendor_template_analyzed",
        company_id=str(company_id),
        vendor_name=vendor_name,
        reused=result["reused"],
        pool_id=result["pool_id"],
    )
    return {
        "message": "공유 풀 재사용" if result["reused"] else "신규 분석 완료",
        **result,
    }


@router.get("/lookup")
async def lookup_vendor_pool(
    vendor_business_number: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """사업자번호로 공유 풀 조회."""
    pool = await _analyzer.lookup_pool(db, vendor_business_number)
    if not pool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="공유 풀에 없는 업체입니다.")
    return {
        "pool_id": str(pool.id),
        "vendor_name": pool.vendor_name,
        "vendor_business_number": pool.vendor_business_number,
        "file_format": pool.file_format,
        "verified": pool.verified,
        "verified_count": pool.verified_count,
        "field_map": pool.field_map,
        "layout_map": pool.layout_map,
    }


@router.get("/company/{company_id}")
async def list_company_vendor_templates(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """고객사가 등록한 업체 템플릿 목록."""
    return await _analyzer.list_company_templates(db, company_id)


@router.post("/{pool_id}/remap")
async def remap_vendor_template(
    pool_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    기존 풀 항목의 셀 매핑을 Claude API로 재분석.
    '_mapping_status: mapping_required' 상태인 XLSX 파일에 사용.
    """
    result = await db.execute(select(VendorTemplatePool).where(VendorTemplatePool.id == pool_id))
    pool = result.scalar_one_or_none()
    if not pool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="풀 항목을 찾을 수 없습니다.")

    if not pool.sample_file_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="샘플 파일이 없습니다. 파일을 다시 업로드하세요.")

    mapper = XlsxCellMapper(get_llm_service())
    mapper_result = await mapper.analyze(pool.sample_file_path)
    cell_map = mapper_result.get("cell_map", {})

    pool.cell_map = cell_map
    pool.field_map = {
        **pool.field_map,
        "_cell_map": cell_map,
        "_mapping_status": "auto_mapped",
    }
    await db.flush()

    logger.info("vendor_pool_remapped", pool_id=str(pool_id))
    return {
        "message": "셀 매핑 완료",
        "pool_id": str(pool_id),
        "cell_map": cell_map,
    }
