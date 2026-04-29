from __future__ import annotations

import uuid

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database import get_db
from app.models.document import GeneratedDocument
from app.models.enums import CategoryType, DocumentType
from app.models.template import Template
from app.schemas.layout_map import LAYOUT_DRAFTS, LayoutMap
from app.schemas.render_profile import RenderProfile, STRATEGY_EXAMPLES
from app.schemas.template import TemplateRead, TemplateUpdate
from app.services.template_service import TemplateService

router = APIRouter(tags=["templates"])
logger = get_logger(__name__)
_template_service = TemplateService()


@router.get("/", response_model=list[TemplateRead])
async def list_templates(
    category_type: CategoryType | None = None,
    document_type: DocumentType | None = None,
    active_only: bool = True,
    project_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[Template]:
    stmt = select(Template)
    if category_type:
        stmt = stmt.where(Template.category_type == category_type)
    if document_type:
        stmt = stmt.where(Template.document_type == document_type)
    if active_only:
        stmt = stmt.where(Template.is_active == True)
    if project_id is not None:
        stmt = stmt.where(Template.project_id == project_id)
    stmt = stmt.order_by(Template.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/", response_model=TemplateRead, status_code=status.HTTP_201_CREATED)
async def upload_template(
    name: str = Form(...),
    category_type: CategoryType = Form(...),
    document_type: DocumentType = Form(...),
    version: str = Form("1.0.0"),
    description: str | None = Form(None),
    project_id: uuid.UUID | None = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> Template:
    content = await file.read()
    original_filename = file.filename or "template"

    _template_service.validate_file(original_filename, content)
    safe_filename, file_path = _template_service.save_file(original_filename, content)
    field_map = _template_service.extract_placeholders(file_path)

    layout_map = _template_service.build_layout_map(file_path)
    ext = Path(original_filename).suffix.lower()
    if ext == ".docx":
        file_format = "docx"
        render_profile = {
            "engine": "docxtpl",
            "preserve_formatting": True,
            "fill_strategy": "placeholder",
            "output_format": "docx",
        }
    elif ext in (".pdf", ".jpg", ".jpeg", ".png"):
        file_format = ext.lstrip(".")
        render_profile = {
            "engine": "passthrough",
            "preserve_formatting": True,
            "fill_strategy": "passthrough_copy",
            "output_format": file_format,
        }
    else:
        file_format = ext.lstrip(".")
        render_profile = {
            "engine": "openpyxl",
            "preserve_formatting": True,
            "fill_strategy": "cell_value",
            "output_format": file_format,
            "sheet_count": len(layout_map.get("sheets", [])),
        }

    template = Template(
        id=uuid.uuid4(),
        name=name,
        category_type=category_type,
        document_type=document_type,
        filename=safe_filename,
        file_path=file_path,
        file_format=file_format,
        version=version,
        field_map=field_map,
        layout_map=layout_map,
        render_profile=render_profile,
        is_active=True,
        description=description,
        project_id=project_id,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)

    logger.info(
        "template_uploaded",
        template_id=str(template.id),
        category=category_type.value,
        doc_type=document_type.value,
        placeholders=len(field_map),
    )
    return template


@router.get("/fields/registry")
async def get_field_registry() -> dict:
    """지원 필드 레지스트리 조회 (UI 셀 매핑 설정 화면용)"""
    return {
        "fields": [
            {"key": k, **v}
            for k, v in _FIELD_REGISTRY.items()
        ]
    }


@router.get("/{template_id}", response_model=TemplateRead)
async def get_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Template:
    template = await _get_or_404(template_id, db)
    return template


@router.patch("/{template_id}", response_model=TemplateRead)
async def update_template(
    template_id: uuid.UUID,
    payload: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
) -> Template:
    template = await _get_or_404(template_id, db)
    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(template, field, value)
    await db.flush()
    await db.refresh(template)
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    template = await _get_or_404(template_id, db)
    await db.execute(
        update(GeneratedDocument)
        .where(GeneratedDocument.template_id == template_id)
        .values(template_id=None)
    )
    _template_service.delete_file(template.file_path)
    await db.delete(template)


@router.get("/{template_id}/fields")
async def get_template_fields(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    template = await _get_or_404(template_id, db)
    return {
        "template_id": str(template.id),
        "template_name": template.name,
        "file_format": template.file_format,
        "field_map": template.field_map,
        "layout_map": template.layout_map,
        "render_profile": template.render_profile,
    }


# 지원 필드 레지스트리: 한국어 레이블 + 타입 + 기본 필수 여부
_FIELD_REGISTRY: dict[str, dict] = {
    "company_name":          {"label": "업체명",       "type": "text",   "required": True},
    "execution_date":        {"label": "집행일자",      "type": "date",   "required": True},
    "budget_item":           {"label": "예산항목",      "type": "text",   "required": True},
    "note":                  {"label": "비고",          "type": "text",   "required": False},
    "item_name":             {"label": "품명",          "type": "text",   "required": True},
    "quantity":              {"label": "수량",          "type": "number", "required": True},
    "unit_price":            {"label": "단가",          "type": "number", "required": True},
    "amount":                {"label": "금액",          "type": "number", "required": True},
    "project_name":          {"label": "과제명",        "type": "text",   "required": False},
    "vendor_registration":   {"label": "사업자등록번호","type": "text",   "required": False},
    "spec":                  {"label": "규격",          "type": "text",   "required": False},
    "total_vat":             {"label": "부가세",        "type": "number", "required": False},
    "total_supply_amount":   {"label": "공급가액",      "type": "number", "required": False},
    "execution_type":        {"label": "집행구분",      "type": "text",   "required": False},
    "manager_name":          {"label": "담당자명",      "type": "text",   "required": False},
    "project_number":        {"label": "과제번호",      "type": "text",   "required": False},
    "delivery_date":         {"label": "납품일자",      "type": "date",   "required": False},
    "project_period":        {"label": "연구기간",      "type": "text",   "required": False},
    "usage_purpose":         {"label": "사용목적",      "type": "text",   "required": False},
    "purchase_purpose":      {"label": "구매목적",      "type": "text",   "required": False},
    "remark":                {"label": "비고(품목)",    "type": "text",   "required": False},
    "total_amount":          {"label": "합계금액",      "type": "number", "required": False},
    "vendor_name":           {"label": "업체명(거래처)", "type": "text",  "required": False},
    "budget_item_checkbox":  {"label": "예산항목(체크박스)", "type": "text", "required": False},
}


class CellMappingRequest(BaseModel):
    """
    XLSX 템플릿 필드 → 셀 주소 매핑 설정.
    {"company_name": "B4", "execution_date": "D6", "amount": "F10"}
    - 레지스트리에 있는 필드는 label/type 자동 적용
    - 없는 필드도 허용 (커스텀 필드)
    - source 등 메타는 _meta 서브키로 분리
    """
    mapping: dict[str, str]


@router.put("/{template_id}/cell-mapping", response_model=TemplateRead)
async def set_cell_mapping(
    template_id: uuid.UUID,
    payload: CellMappingRequest,
    db: AsyncSession = Depends(get_db),
) -> Template:
    """XLSX 템플릿의 필드별 셀 주소를 저장한다."""
    template = await _get_or_404(template_id, db)

    current_map: dict = dict(template.field_map or {})

    for field_key, cell_address in payload.mapping.items():
        cell_address = cell_address.strip().upper()
        registry = _FIELD_REGISTRY.get(field_key, {})

        if field_key in current_map and isinstance(current_map[field_key], dict):
            existing = current_map[field_key]
            existing["cell"] = cell_address
            # label/type은 레지스트리 값으로 갱신, 없으면 기존 유지
            if registry:
                existing.setdefault("label", registry["label"])
                existing.setdefault("type", registry["type"])
                existing.setdefault("required", registry["required"])
            # source → _meta로 이전
            if "source" in existing:
                existing.setdefault("_meta", {})["source"] = existing.pop("source")
        else:
            entry: dict = {
                "label":    registry.get("label",    field_key.replace("_", " ").title()),
                "type":     registry.get("type",     "text"),
                "required": registry.get("required", False),
                "cell":     cell_address,
            }
            current_map[field_key] = entry

    template.field_map = current_map
    await db.flush()
    await db.refresh(template)

    logger.info(
        "cell_mapping_saved",
        template_id=str(template_id),
        fields=list(payload.mapping.keys()),
    )
    return template


@router.get("/{template_id}/render-profile")
async def get_render_profile(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """저장된 render_profile 조회. 없으면 null 반환."""
    template = await _get_or_404(template_id, db)
    return {
        "template_id": str(template_id),
        "document_type": template.document_type.value,
        "render_profile": template.render_profile,
        "strategy_examples": STRATEGY_EXAMPLES,
    }


@router.put("/{template_id}/render-profile", response_model=TemplateRead)
async def set_render_profile(
    template_id: uuid.UUID,
    payload: RenderProfile,
    db: AsyncSession = Depends(get_db),
) -> Template:
    """render_profile 저장. 기존 field_map / layout_map 은 변경하지 않는다."""
    template = await _get_or_404(template_id, db)
    template.render_profile = payload.to_dict()
    await db.flush()
    await db.refresh(template)
    logger.info(
        "render_profile_saved",
        template_id=str(template_id),
        doc_type=payload.doc_type,
        render_strategy=payload.render_strategy,
    )
    return template


@router.delete("/{template_id}/render-profile", response_model=TemplateRead)
async def clear_render_profile(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Template:
    """render_profile 초기화 (자동감지 fallback으로 되돌림)."""
    template = await _get_or_404(template_id, db)
    template.render_profile = None
    await db.flush()
    await db.refresh(template)
    return template


@router.get("/layouts/drafts")
async def get_layout_drafts() -> dict:
    """문서 타입별 layout_map 구조 초안 조회."""
    return {
        doc_type: layout.to_dict()
        for doc_type, layout in LAYOUT_DRAFTS.items()
    }


@router.get("/{template_id}/layout-map")
async def get_layout_map(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """저장된 layout_map 조회. 없으면 해당 document_type 초안 반환."""
    template = await _get_or_404(template_id, db)
    if template.layout_map:
        return {"template_id": str(template_id), "layout_map": template.layout_map, "source": "saved"}
    draft = LAYOUT_DRAFTS.get(template.document_type.value)
    if draft:
        return {"template_id": str(template_id), "layout_map": draft.to_dict(), "source": "draft"}
    return {"template_id": str(template_id), "layout_map": None, "source": "none"}


@router.put("/{template_id}/layout-map", response_model=TemplateRead)
async def set_layout_map(
    template_id: uuid.UUID,
    payload: LayoutMap,
    db: AsyncSession = Depends(get_db),
) -> Template:
    """layout_map 저장. field_map은 변경하지 않는다."""
    template = await _get_or_404(template_id, db)
    template.layout_map = payload.to_dict()
    await db.flush()
    await db.refresh(template)
    logger.info("layout_map_saved", template_id=str(template_id), document_type=payload.document_type)
    return template


@router.post("/{template_id}/remap", response_model=TemplateRead)
async def remap_template_cells(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Template:
    """XLSX 템플릿의 셀 좌표를 Claude API로 자동 분석."""
    from app.services.llm_service import get_llm_service
    from app.services.xlsx_cell_mapper import XlsxCellMapper

    template = await _get_or_404(template_id, db)

    ext = Path(template.file_path).suffix.lower()
    if ext not in (".xlsx", ".xls"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="XLSX/XLS 파일만 셀 매핑 가능합니다.",
        )

    mapper = XlsxCellMapper(get_llm_service())
    result = await mapper.analyze(template.file_path)
    cell_map = result.get("cell_map", {})

    template.field_map = {
        **template.field_map,
        "_cell_map": cell_map,
        "_mapping_status": "auto_mapped",
    }
    await db.flush()
    await db.refresh(template)

    logger.info("template_remapped", template_id=str(template_id))
    return template


async def _get_or_404(template_id: uuid.UUID, db: AsyncSession) -> Template:
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"템플릿 ID {template_id}를 찾을 수 없습니다.",
        )
    return template
