from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.vendor_pool import CompanyVendorTemplate, VendorTemplatePool
from app.services.document_extractor_service import DocumentExtractorService
from app.services.llm_service import get_llm_service
from app.services.template_service import TemplateService
from app.services.xlsx_cell_mapper import XlsxCellMapper

logger = get_logger(__name__)


class VendorTemplateAnalyzer:
    """
    업체 템플릿 분석 및 공유 풀 관리.

    핵심 흐름:
    1. 파일 업로드
    2. 사업자번호 추출 (DocumentExtractorService 재사용)
    3. 공유 풀 조회
    4. HIT → 기존 layout_map 반환 (Claude API 0원)
    5. MISS → 신규 분석 → 풀 저장
    """

    def __init__(self) -> None:
        self._extractor = DocumentExtractorService()
        self._template_svc = TemplateService()
        self._cell_mapper = XlsxCellMapper(get_llm_service())

    # ─── 공개 API ─────────────────────────────────────────────────────────

    async def analyze_and_register(
        self,
        db: AsyncSession,
        file_path: str,
        filename: str,
        vendor_name: str,
        company_id: uuid.UUID,
    ) -> dict[str, Any]:
        """
        업체 템플릿 파일을 분석하고 공유 풀에 등록한다.

        반환값:
        {
            "pool_id": str,
            "vendor_business_number": str | None,
            "layout_map": dict,
            "render_profile": dict,
            "field_map": dict,
            "file_format": str,
            "reused": bool,
            "company_template_id": str,
        }
        """
        extracted = self._extractor.extract(file_path, filename)
        biz_num = extracted.get("vendor_registration_number")

        existing_pool: VendorTemplatePool | None = None
        if biz_num:
            existing_pool = await self._find_pool_by_biznum(db, biz_num)

        if existing_pool:
            logger.info(
                "vendor_pool_hit",
                vendor_name=vendor_name,
                biz_num=biz_num,
                pool_id=str(existing_pool.id),
                verified_count=existing_pool.verified_count,
            )
            pool = existing_pool
            reused = True
        else:
            layout_map = self._template_svc.build_layout_map(file_path)
            field_map = self._template_svc.extract_placeholders(file_path)
            ext = Path(filename).suffix.lower()
            file_format = ext.lstrip(".")
            render_profile = self._build_render_profile(ext, layout_map)

            # XLSX/XLS 파일이면 Claude API로 셀 좌표 자동 분석
            if ext in (".xlsx", ".xls"):
                try:
                    mapper_result = await self._cell_mapper.analyze(file_path)
                    cell_map = mapper_result.get("cell_map", {})
                    field_map["_cell_map"] = cell_map
                    field_map["_mapping_status"] = "auto_mapped"
                    logger.info(
                        "xlsx_cell_map_merged",
                        vendor_name=vendor_name,
                        has_items_table=bool(cell_map.get("items_table")),
                    )
                except Exception as e:
                    logger.warning("xlsx_cell_map_failed", error=str(e))
                    field_map["_mapping_status"] = "mapping_required"

            pool = VendorTemplatePool(
                id=uuid.uuid4(),
                vendor_business_number=biz_num or f"UNKNOWN_{uuid.uuid4().hex[:8]}",
                vendor_name=vendor_name,
                file_format=file_format,
                layout_map=layout_map,
                render_profile=render_profile,
                field_map=field_map,
                verified=False,
                verified_count=0,
                sample_file_path=file_path,
            )
            db.add(pool)
            await db.flush()
            reused = False

            logger.info(
                "vendor_pool_created",
                vendor_name=vendor_name,
                biz_num=biz_num,
                pool_id=str(pool.id),
                file_format=file_format,
            )

        company_template = await self._upsert_company_template(db, company_id, pool.id)
        pool.verified_count = await self._count_companies(db, pool.id)
        await db.flush()

        return {
            "pool_id": str(pool.id),
            "vendor_business_number": pool.vendor_business_number,
            "layout_map": pool.layout_map,
            "render_profile": pool.render_profile,
            "field_map": pool.field_map,
            "file_format": pool.file_format,
            "reused": reused,
            "company_template_id": str(company_template.id),
        }

    async def lookup_pool(
        self, db: AsyncSession, vendor_business_number: str
    ) -> VendorTemplatePool | None:
        """사업자번호로 공유 풀 조회 (읽기 전용)."""
        return await self._find_pool_by_biznum(db, vendor_business_number)

    async def list_company_templates(
        self, db: AsyncSession, company_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        """고객사가 등록한 업체 템플릿 목록."""
        result = await db.execute(
            select(CompanyVendorTemplate, VendorTemplatePool)
            .join(VendorTemplatePool, CompanyVendorTemplate.pool_id == VendorTemplatePool.id)
            .where(
                CompanyVendorTemplate.company_id == company_id,
                CompanyVendorTemplate.is_active == True,
            )
            .order_by(CompanyVendorTemplate.created_at.desc())
        )
        return [
            {
                "company_template_id": str(ct.id),
                "pool_id": str(pool.id),
                "vendor_name": ct.vendor_alias or pool.vendor_name,
                "vendor_business_number": pool.vendor_business_number,
                "file_format": pool.file_format,
                "verified": pool.verified,
                "verified_count": pool.verified_count,
                "field_map": {**pool.field_map, **ct.custom_override},
                "layout_map": pool.layout_map,
                "render_profile": pool.render_profile,
            }
            for ct, pool in result.all()
        ]

    # ─── 내부 헬퍼 ────────────────────────────────────────────────────────

    async def _find_pool_by_biznum(
        self, db: AsyncSession, biz_num: str
    ) -> VendorTemplatePool | None:
        normalized = self._normalize_biznum(biz_num)
        result = await db.execute(
            select(VendorTemplatePool).where(
                VendorTemplatePool.vendor_business_number == normalized
            )
        )
        return result.scalar_one_or_none()

    async def _upsert_company_template(
        self, db: AsyncSession, company_id: uuid.UUID, pool_id: uuid.UUID
    ) -> CompanyVendorTemplate:
        result = await db.execute(
            select(CompanyVendorTemplate).where(
                CompanyVendorTemplate.company_id == company_id,
                CompanyVendorTemplate.pool_id == pool_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        ct = CompanyVendorTemplate(
            id=uuid.uuid4(),
            company_id=company_id,
            pool_id=pool_id,
            custom_override={},
            is_active=True,
        )
        db.add(ct)
        await db.flush()
        return ct

    async def _count_companies(self, db: AsyncSession, pool_id: uuid.UUID) -> int:
        result = await db.execute(
            select(func.count(CompanyVendorTemplate.id)).where(
                CompanyVendorTemplate.pool_id == pool_id,
                CompanyVendorTemplate.is_active == True,
            )
        )
        return result.scalar_one() or 0

    @staticmethod
    def _normalize_biznum(raw: str) -> str:
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 10:
            return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
        return raw

    @staticmethod
    def _build_render_profile(ext: str, layout_map: dict) -> dict:
        if ext in (".xlsx", ".xls"):
            return {
                "engine": "openpyxl",
                "preserve_formatting": True,
                "fill_strategy": "cell_value",
                "output_format": ext.lstrip("."),
                "sheet_count": len(layout_map.get("sheets", [])),
                "notes": "병합 셀·스타일 절대 변경 금지. 값만 치환.",
            }
        return {
            "engine": "docxtpl",
            "preserve_formatting": True,
            "fill_strategy": "placeholder",
            "output_format": "docx",
        }
