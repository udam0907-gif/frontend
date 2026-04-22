"""
Document Set Service — 비목별 문서세트 자동 생성 엔진

문서 소스 매핑 규칙 (고정):
  [업체관리에서 가져오는 문서]
    quote                       → 주업체.quote_template_path
    comparative_quote           → 비교견적업체.quote_template_path
    transaction_statement       → 주업체.transaction_statement_path
    vendor_business_registration → 주업체.business_registration_path (복사)
    vendor_bank_copy            → 주업체.bank_copy_path (복사)

  [템플릿관리에서 가져오는 문서]
    expense_resolution, inspection_confirmation, service_contract,
    work_order, cash/in_kind_expense_resolution, researcher_status_sheet,
    receipt, meeting_minutes, inspection_photos 등 내부 공통 양식

원칙:
  - AI가 문서 내용을 생성하거나 양식 구조를 수정하지 않음
  - 비교견적서: 원금액 × 1.1 고정
  - 업로드된 원본 양식 파일이 없으면 해당 문서는 상태를 정확히 표시
"""

from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import DocumentGenerationError
from app.core.logging import get_logger
from app.models.document import GeneratedDocument
from app.models.enums import CategoryType, DocumentType
from app.models.expense import ExpenseItem
from app.models.project import Project
from app.models.template import Template
from app.models.vendor import Vendor
from app.services.document_generator import DocumentGenerator
from app.services.llm_service import get_llm_service

logger = get_logger(__name__)

# ─── 비목별 필수 문서세트 (고정) ────────────────────────────────────────────

DOCUMENT_SETS: dict[CategoryType, list[DocumentType]] = {
    CategoryType.materials: [
        DocumentType.quote,
        DocumentType.comparative_quote,
        DocumentType.expense_resolution,
        DocumentType.inspection_confirmation,
        DocumentType.vendor_business_registration,
        DocumentType.vendor_bank_copy,
    ],
    CategoryType.outsourcing: [
        DocumentType.quote,
        DocumentType.comparative_quote,
        DocumentType.service_contract,
        DocumentType.work_order,
        DocumentType.transaction_statement,
        DocumentType.inspection_photos,
        DocumentType.vendor_business_registration,
        DocumentType.vendor_bank_copy,
    ],
    CategoryType.labor: [
        DocumentType.cash_expense_resolution,
        DocumentType.in_kind_expense_resolution,
        DocumentType.researcher_status_sheet,
    ],
    CategoryType.test_report: [
        DocumentType.quote,
        DocumentType.expense_resolution,
        DocumentType.transaction_statement,
    ],
    CategoryType.meeting: [
        DocumentType.receipt,
        DocumentType.meeting_minutes,
    ],
}

# 업체 파일에서 바이너리 복사하는 문서 (렌더링 없음)
VENDOR_COPY_DOCS: dict[DocumentType, str] = {
    DocumentType.vendor_business_registration: "business_registration_path",
    DocumentType.vendor_bank_copy: "bank_copy_path",
}

# 주업체 파일을 렌더링 소스로 사용하는 문서
VENDOR_TEMPLATE_DOCS: dict[DocumentType, str] = {
    DocumentType.quote: "quote_template_path",
    DocumentType.transaction_statement: "transaction_statement_path",
}

# 비교견적서: 비교견적업체의 quote_template_path 사용
COMPARATIVE_DOC = DocumentType.comparative_quote

# 비교견적 금액 배율
COMPARATIVE_MULTIPLIER = Decimal("1.1")

# CategoryType → 지출결의서 체크박스 레이블 매핑
_CATEGORY_LABEL: dict[str, str] = {
    "materials":   "연구재료비",
    "labor":       "인건비",
    "outsourcing": "연구활동비",
    "meeting":     "연구활동비",
    "test_report": "연구활동비",
    "other":       "간접비",
}

# 지출결의서 체크박스 항목 순서 (유담 양식 기준)
_CHECKBOX_ITEMS = ["연구재료비", "인건비", "연구활동비", "간접비", "연구수당"]


def _make_budget_checkbox(category_type: CategoryType) -> str:
    """선택된 항목에 ■, 나머지에 □를 붙여 전체 체크박스 문자열 반환."""
    label = _CATEGORY_LABEL.get(category_type.value, "")
    return "   ".join(
        f"{'■' if item == label else '□'} {item}"
        for item in _CHECKBOX_ITEMS
    )


# 내부 템플릿(과제 공통 양식)에서 가져오는 문서 (위에 없는 모든 나머지)
# = Template 테이블에서 조회


@dataclass
class DocSetItem:
    document_type: DocumentType
    # 상태 코드
    # "excel_rendered"            — XLSX 셀 매핑으로 값 입력 완료 (업체 양식 포함)
    # "vendor_attachment_included"— 업체 파일 바이너리 첨부 (사업자등록증/통장사본 등)
    # "mapping_needed"            — XLSX이지만 셀 매핑 미설정 (원본 복사)
    # "render_failed"             — 렌더링 중 예외 발생
    # "template_missing"          — 어떤 소스에서도 파일을 찾지 못함
    # "vendor_file_missing"       — 업체가 없거나 파일 슬롯이 비어 있음
    # is_vendor_doc 플래그로 업체 양식 여부를 별도 표시 (상태값과 독립)
    status: str
    output_path: str | None = None
    generated_document_id: uuid.UUID | None = None
    error_message: str | None = None
    is_vendor_doc: bool = False


@dataclass
class DocumentSetResult:
    expense_item_id: uuid.UUID
    category_type: CategoryType
    items: list[DocSetItem] = field(default_factory=list)

    @property
    def generated_count(self) -> int:
        return sum(
            1 for i in self.items
            if i.status in ("excel_rendered", "vendor_attachment_included", "mapping_needed")
        )

    @property
    def error_count(self) -> int:
        return sum(
            1 for i in self.items
            if i.status in ("template_missing", "vendor_file_missing", "render_failed")
        )

    @property
    def all_generated(self) -> bool:
        return self.error_count == 0


class DocumentSetService:
    def __init__(self, storage_path: str) -> None:
        self._vendor_copies_path = Path(storage_path) / "vendor_copies"
        self._vendor_copies_path.mkdir(parents=True, exist_ok=True)

    async def generate_set(
        self,
        expense_id: uuid.UUID,
        db: AsyncSession,
    ) -> DocumentSetResult:
        expense = await self._load_expense(expense_id, db)
        project = await self._load_project(expense.project_id, db)

        meta = expense.metadata_ or {}

        # 주업체: vendor_id 우선, 없으면 vendor_name으로 조회
        vendor = await self._load_vendor(
            vendor_id=meta.get("vendor_id"),
            vendor_name=expense.vendor_name,
            project_id=expense.project_id,
            db=db,
        )

        # 비교견적업체: compare_vendor_id로 조회
        compare_vendor_id = meta.get("compare_vendor_id")
        compare_vendor = await self._load_vendor(
            vendor_id=compare_vendor_id,
            vendor_name=None,
            project_id=expense.project_id,
            db=db,
        )
        logger.info(
            "compare_vendor_lookup",
            expense_id=str(expense_id),
            compare_vendor_id=compare_vendor_id,
            found=compare_vendor is not None,
            has_quote_template=bool(compare_vendor and compare_vendor.quote_template_path),
        )

        required_docs = DOCUMENT_SETS.get(expense.category_type, [])
        base_context = self._build_context(expense, project)

        result = DocumentSetResult(
            expense_item_id=expense_id,
            category_type=expense.category_type,
        )

        generator = DocumentGenerator(get_llm_service())
        batch_id = str(uuid.uuid4())

        for doc_type in required_docs:
            item = await self._process_doc(
                doc_type=doc_type,
                expense=expense,
                vendor=vendor,
                compare_vendor=compare_vendor,
                base_context=base_context,
                project_data=self._project_data(project),
                generator=generator,
                db=db,
                batch_id=batch_id,
            )
            result.items.append(item)
            logger.info(
                "doc_set_item",
                expense_id=str(expense_id),
                doc_type=doc_type.value,
                status=item.status,
            )

        return result

    async def _process_doc(
        self,
        doc_type: DocumentType,
        expense: ExpenseItem,
        vendor: Vendor | None,
        compare_vendor: Vendor | None,
        base_context: dict[str, Any],
        project_data: dict[str, Any],
        generator: DocumentGenerator,
        db: AsyncSession,
        batch_id: str = "",
    ) -> DocSetItem:

        # ① 업체 바이너리 복사 (사업자등록증 / 통장사본)
        if doc_type in VENDOR_COPY_DOCS:
            return await self._include_vendor_copy(doc_type, vendor, expense, db, batch_id)

        # ② 주업체 원본 양식 문서 (견적서 / 거래명세서)
        if doc_type in VENDOR_TEMPLATE_DOCS:
            return await self._process_vendor_template(
                doc_type=doc_type,
                vendor=vendor,
                expense=expense,
                context=base_context,
                project_data=project_data,
                generator=generator,
                db=db,
                batch_id=batch_id,
            )

        # ③ 비교견적서 — 비교견적업체의 견적서 원본 양식 사용
        if doc_type == COMPARATIVE_DOC:
            return await self._process_comparative(
                expense=expense,
                compare_vendor=compare_vendor,
                base_context=base_context,
                project_data=project_data,
                generator=generator,
                db=db,
                batch_id=batch_id,
            )

        # ④ 내부 공통 양식 — 템플릿관리(Template 테이블)에서 조회
        template = await self._find_template(
            category_type=expense.category_type,
            document_type=doc_type,
            project_id=expense.project_id,
            db=db,
        )
        if not template:
            return DocSetItem(
                document_type=doc_type,
                status="template_missing",
                error_message=f"내부 템플릿 미등록: {doc_type.value}",
            )

        return await self._render_from_template(
            doc_type=doc_type,
            template_path=template.file_path,
            field_map=template.field_map,
            context=base_context,
            project_data=project_data,
            expense=expense,
            template_id=str(template.id),
            generator=generator,
            db=db,
            is_vendor_doc=False,
            db_template_id=template.id,
            batch_id=batch_id,
        )

    # ─── 업체 바이너리 복사 ──────────────────────────────────────────────────

    async def _include_vendor_copy(
        self,
        doc_type: DocumentType,
        vendor: Vendor | None,
        expense: ExpenseItem,
        db: AsyncSession,
        batch_id: str = "",
    ) -> DocSetItem:
        if not vendor:
            return DocSetItem(
                document_type=doc_type,
                status="vendor_file_missing",
                error_message="업체가 등록되지 않았습니다.",
                is_vendor_doc=True,
            )
        attr = VENDOR_COPY_DOCS[doc_type]
        source_path = getattr(vendor, attr, None)
        if not source_path or not Path(source_path).exists():
            return DocSetItem(
                document_type=doc_type,
                status="vendor_file_missing",
                error_message=f"업체 파일 미등록: {attr}",
                is_vendor_doc=True,
            )
        dest_name = f"{expense.id}_{doc_type.value}_{Path(source_path).name}"
        dest_path = str(self._vendor_copies_path / dest_name)
        shutil.copy2(source_path, dest_path)

        gen_doc = GeneratedDocument(
            id=uuid.uuid4(),
            expense_item_id=expense.id,
            template_id=None,
            output_path=dest_path,
            generation_trace={"render_mode": "vendor_attachment_included", "source": attr, "document_type": doc_type.value, "batch_id": batch_id},
            is_valid=True,
        )
        db.add(gen_doc)
        await db.flush()

        return DocSetItem(
            document_type=doc_type,
            status="vendor_attachment_included",
            output_path=dest_path,
            generated_document_id=gen_doc.id,
            is_vendor_doc=True,
        )

    # ─── 업체 원본 양식 렌더링 (quote / transaction_statement) ──────────────

    async def _process_vendor_template(
        self,
        doc_type: DocumentType,
        vendor: Vendor | None,
        expense: ExpenseItem,
        context: dict[str, Any],
        project_data: dict[str, Any],
        generator: DocumentGenerator,
        db: AsyncSession,
        batch_id: str = "",
    ) -> DocSetItem:
        if not vendor:
            return DocSetItem(
                document_type=doc_type,
                status="vendor_file_missing",
                error_message="업체가 등록되지 않았습니다.",
                is_vendor_doc=True,
            )
        attr = VENDOR_TEMPLATE_DOCS[doc_type]
        file_path = getattr(vendor, attr, None)
        if not file_path or not Path(file_path).exists():
            return DocSetItem(
                document_type=doc_type,
                status="vendor_file_missing",
                error_message=f"업체 원본 양식 미등록: {attr}",
                is_vendor_doc=True,
            )
        # 같은 document_type의 DB 템플릿 field_map을 vendor 파일에 적용
        db_template = await self._find_template(
            category_type=expense.category_type,
            document_type=doc_type,
            project_id=expense.project_id,
            db=db,
        )
        field_map = db_template.field_map if db_template else {}

        return await self._render_from_template(
            doc_type=doc_type,
            template_path=file_path,
            field_map=field_map,
            context=context,
            project_data=project_data,
            expense=expense,
            template_id=f"vendor_{vendor.id}",
            generator=generator,
            db=db,
            is_vendor_doc=True,
            batch_id=batch_id,
        )

    # ─── 비교견적서 ─────────────────────────────────────────────────────────

    async def _process_comparative(
        self,
        expense: ExpenseItem,
        compare_vendor: Vendor | None,
        base_context: dict[str, Any],
        project_data: dict[str, Any],
        generator: DocumentGenerator,
        db: AsyncSession,
        batch_id: str = "",
    ) -> DocSetItem:
        if not compare_vendor:
            return DocSetItem(
                document_type=COMPARATIVE_DOC,
                status="vendor_file_missing",
                error_message="비교견적업체가 선택되지 않았습니다.",
                is_vendor_doc=True,
            )
        file_path = compare_vendor.quote_template_path
        if not file_path or not Path(file_path).exists():
            return DocSetItem(
                document_type=COMPARATIVE_DOC,
                status="vendor_file_missing",
                error_message=f"선택한 비교업체({compare_vendor.name})에 견적서 파일이 없습니다.",
                is_vendor_doc=True,
            )

        # 비교견적 금액: meta의 compare_amount 우선, 없으면 × 1.1
        meta = expense.metadata_ or {}
        if "compare_amount" in meta:
            compare_amount = int(meta["compare_amount"])
        else:
            original = Decimal(str(expense.amount))
            compare_amount = int((original * COMPARATIVE_MULTIPLIER).quantize(Decimal("1")))

        context = dict(base_context)
        context["amount"] = compare_amount
        context["total_amount"] = compare_amount
        context["unit_price"] = compare_amount
        context["vendor_name"] = compare_vendor.name
        context["company_name"] = compare_vendor.name   # alias
        context["comparative_note"] = (
            f"비교견적 ({compare_vendor.name} · 원견적 {int(expense.amount):,}원 기준 10% 인상)"
        )

        # quote 문서 유형의 DB field_map을 비교견적서에도 적용
        db_template = await self._find_template(
            category_type=expense.category_type,
            document_type=DocumentType.quote,
            project_id=expense.project_id,
            db=db,
        )
        field_map = db_template.field_map if db_template else {}

        return await self._render_from_template(
            doc_type=COMPARATIVE_DOC,
            template_path=file_path,
            field_map=field_map,
            context=context,
            project_data=project_data,
            expense=expense,
            template_id=f"compare_vendor_{compare_vendor.id}",
            generator=generator,
            db=db,
            is_vendor_doc=True,
            batch_id=batch_id,
        )

    # ─── 공통 렌더 호출 ─────────────────────────────────────────────────────

    async def _render_from_template(
        self,
        doc_type: DocumentType,
        template_path: str,
        field_map: dict[str, Any],
        context: dict[str, Any],
        project_data: dict[str, Any],
        expense: ExpenseItem,
        template_id: str,
        generator: DocumentGenerator,
        db: AsyncSession | None,
        is_vendor_doc: bool,
        db_template_id: uuid.UUID | None = None,
        batch_id: str = "",
    ) -> DocSetItem:
        try:
            gen_result = await generator.generate(
                template_path=template_path,
                field_map=field_map,
                user_values=context,
                project_data=project_data,
                expense_item_id=str(expense.id),
                template_id=template_id,
                document_type=doc_type.value,
            )

            render_mode = gen_result.get("render_mode", "")

            # render_mode → status 매핑
            if render_mode == "docx_rendered":
                final_status = "docx_rendered"
            elif render_mode == "excel_rendered":
                final_status = "excel_rendered"
            elif render_mode == "mapping_needed":
                final_status = "mapping_needed"
            elif render_mode == "passthrough_copy":
                final_status = "vendor_attachment_included" if is_vendor_doc else "mapping_needed"
            else:
                final_status = "excel_rendered"

            gen_doc_id: uuid.UUID | None = None
            if db is not None:
                trace = dict(gen_result["generation_trace"])
                trace["document_type"] = doc_type.value
                trace["batch_id"] = batch_id
                gen_doc = GeneratedDocument(
                    id=uuid.uuid4(),
                    expense_item_id=expense.id,
                    template_id=db_template_id,  # None for vendor-based docs
                    output_path=gen_result["output_path"],
                    generation_trace=trace,
                    is_valid=True,
                )
                db.add(gen_doc)
                await db.flush()
                gen_doc_id = gen_doc.id

            return DocSetItem(
                document_type=doc_type,
                status=final_status,
                output_path=gen_result["output_path"],
                generated_document_id=gen_doc_id,
                is_vendor_doc=is_vendor_doc,
            )

        except Exception as e:
            logger.error(
                "doc_set_generation_error",
                expense_id=str(expense.id),
                doc_type=doc_type.value,
                error=str(e),
            )
            return DocSetItem(
                document_type=doc_type,
                status="render_failed",
                error_message=str(e),
                is_vendor_doc=is_vendor_doc,
            )

    # ─── 헬퍼: 컨텍스트 빌드 ─────────────────────────────────────────────────

    def _build_context(self, expense: ExpenseItem, project: Project) -> dict[str, Any]:
        meta = expense.metadata_ or {}
        ctx: dict[str, Any] = {
            "expense_date":       expense.expense_date or "",
            "vendor_name":        expense.vendor_name or "",
            "vendor_registration":expense.vendor_registration_number or "",
            "amount":             int(expense.amount),
            "total_amount":       int(expense.amount),
            "title":              expense.title,
            "project_name":       project.name,
            "project_code":       project.code,
            "institution":        project.institution,
            "pi_name":            project.principal_investigator,
            "category_type":      expense.category_type.value,  # checkbox 매핑용
        }
        for key, value in meta.items():
            if value is not None and key not in ("vendor_id", "compare_vendor_id", "compare_amount"):
                ctx[key] = value

        # 셀 매핑 field_map 키와 모델 키 간 alias
        ctx.setdefault("company_name",          ctx["vendor_name"])
        ctx.setdefault("execution_date",        ctx["expense_date"])
        # budget_item: 단순 텍스트 레이블 (cfbfee34 단순 양식용)
        cat_label = _CATEGORY_LABEL.get(expense.category_type.value, expense.category_type.value)
        ctx.setdefault("budget_item",           cat_label)
        # budget_item_checkbox: 유담 지출결의서 B9 체크박스 셀용
        ctx.setdefault("budget_item_checkbox",  _make_budget_checkbox(expense.category_type))
        ctx.setdefault("item_name",             ctx.get("product_name") or expense.title)
        return ctx

    def _project_data(self, project: Project) -> dict[str, Any]:
        return {
            "project_name": project.name,
            "project_code": project.code,
            "institution": project.institution,
            "pi_name": project.principal_investigator,
            "period_start": str(project.period_start),
            "period_end": str(project.period_end),
        }

    # ─── DB 로더 ────────────────────────────────────────────────────────────

    async def _load_expense(self, expense_id: uuid.UUID, db: AsyncSession) -> ExpenseItem:
        result = await db.execute(
            select(ExpenseItem)
            .where(ExpenseItem.id == expense_id)
            .options(selectinload(ExpenseItem.documents))
        )
        expense = result.scalar_one_or_none()
        if not expense:
            raise DocumentGenerationError(f"지출 항목을 찾을 수 없습니다: {expense_id}")
        return expense

    async def _load_project(self, project_id: uuid.UUID, db: AsyncSession) -> Project:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise DocumentGenerationError(f"과제를 찾을 수 없습니다: {project_id}")
        return project

    async def _load_vendor(
        self,
        vendor_id: str | None,
        vendor_name: str | None,
        project_id: uuid.UUID,
        db: AsyncSession,
    ) -> Vendor | None:
        if vendor_id:
            try:
                vid = uuid.UUID(str(vendor_id))
                result = await db.execute(
                    select(Vendor).where(Vendor.id == vid, Vendor.project_id == project_id)
                )
                v = result.scalar_one_or_none()
                if v:
                    return v
            except (ValueError, AttributeError):
                pass
        if vendor_name:
            result = await db.execute(
                select(Vendor).where(
                    Vendor.project_id == project_id,
                    Vendor.name == vendor_name,
                )
            )
            return result.scalar_one_or_none()
        return None

    async def _find_template(
        self,
        category_type: CategoryType,
        document_type: DocumentType,
        project_id: uuid.UUID,
        db: AsyncSession,
    ) -> Template | None:
        """과제 전용 → 공용 순으로 템플릿 탐색."""
        result = await db.execute(
            select(Template).where(
                Template.category_type == category_type,
                Template.document_type == document_type,
                Template.project_id == project_id,
                Template.is_active == True,
            ).order_by(Template.created_at.desc()).limit(1)
        )
        template = result.scalar_one_or_none()
        if template:
            return template
        result = await db.execute(
            select(Template).where(
                Template.category_type == category_type,
                Template.document_type == document_type,
                Template.project_id == None,
                Template.is_active == True,
            ).order_by(Template.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()
