"""
업체 문서에서 기본 정보를 자동 추출하는 서비스.

우선순위:
  1순위: 사업자등록증
  2순위: 견적서 / 거래명세서
  3순위: 통장사본 (보조)

지원 형식: DOCX, XLSX, PDF, JPG/JPEG/PNG
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import TypedDict

from app.core.logging import get_logger

logger = get_logger(__name__)

# ─── 정규식 패턴 ─────────────────────────────────────────────────────────────

# 사업자등록번호: 123-45-67890 또는 1234567890
_BIZ_NUM_RE = re.compile(
    r"(?<!\d)"
    r"(\d{3}[-\s]?\d{2}[-\s]?\d{5})"
    r"(?!\d)"
)

# 한국 전화번호
_PHONE_RE = re.compile(
    r"(?<!\d)"
    r"(0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4})"
    r"(?!\d)"
)

# 업체명 앞에 오는 키워드 (뒤에 콜론·공백 포함)
_NAME_LABEL_RE = re.compile(
    r"(?:상호|업체명|회사명|공급자|법인명|사업체명|예금주|수취인|판매자|거래처)"
    r"\s*[:：]?\s*"
    r"([^\n\r\t,、]{2,30})"
)

# 사업자번호 앞 키워드
_BIZ_LABEL_RE = re.compile(
    r"(?:사업자\s*(?:등록)?\s*번호|등록번호|사업자번호)"
    r"\s*[:：]?\s*"
    r"(\d[\d\-\s]{8,13}\d)"
)

# 전화 앞 키워드
_PHONE_LABEL_RE = re.compile(
    r"(?:전화\s*번호|전화|TEL|Tel|연락처|대표번호|팩스\s*제외)"
    r"\s*[:：]?\s*"
    r"(0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4})"
)


# ─── 결과 타입 ───────────────────────────────────────────────────────────────

class ExtractResult(TypedDict):
    vendor_name: str | None
    business_number: str | None
    contact: str | None
    source: str          # 어떤 파서가 추출했는지
    confidence: dict     # per-field confidence (0~1)


def _normalize_biz_num(raw: str) -> str:
    """XXX-XX-XXXXX 형식으로 정규화."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
    return raw.strip()


def _normalize_phone(raw: str) -> str:
    """02-XXX-XXXX / 0XX-XXXX-XXXX 형식으로 정규화."""
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("02") and len(digits) in (9, 10):
        return f"02-{digits[2:-4]}-{digits[-4:]}"
    if len(digits) == 11:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return raw.strip()


# ─── 텍스트에서 필드 추출 ───────────────────────────────────────────────────

def _extract_from_text(text: str) -> dict:
    result: dict = {"vendor_name": None, "business_number": None, "contact": None}
    confidence: dict = {}

    # 업체명: 키워드 + 바로 뒤 값 (고신뢰도)
    m = _NAME_LABEL_RE.search(text)
    if m:
        name = m.group(1).strip().rstrip("(주)(사)(유)").strip()
        if len(name) >= 2:
            result["vendor_name"] = name
            confidence["vendor_name"] = 0.9

    # 사업자번호: 키워드 기반 우선
    m = _BIZ_LABEL_RE.search(text)
    if m:
        result["business_number"] = _normalize_biz_num(m.group(1))
        confidence["business_number"] = 0.95
    else:
        # 키워드 없이 패턴만으로 탐색
        m = _BIZ_NUM_RE.search(text)
        if m:
            result["business_number"] = _normalize_biz_num(m.group(1))
            confidence["business_number"] = 0.7

    # 연락처: 키워드 기반 우선
    m = _PHONE_LABEL_RE.search(text)
    if m:
        result["contact"] = _normalize_phone(m.group(1))
        confidence["contact"] = 0.9
    else:
        m = _PHONE_RE.search(text)
        if m:
            # 사업자번호처럼 보이는 숫자 제외
            phone = m.group(1)
            if not _BIZ_NUM_RE.fullmatch(re.sub(r"\D", "", phone).ljust(10)):
                result["contact"] = _normalize_phone(phone)
                confidence["contact"] = 0.65

    result["_confidence"] = confidence
    return result


# ─── 파서: DOCX ─────────────────────────────────────────────────────────────

def _extract_docx(data: bytes) -> tuple[str, dict]:
    import io
    from docx import Document as DocxDoc
    try:
        doc = DocxDoc(io.BytesIO(data))
    except Exception as e:
        return "", {}
    lines: list[str] = []
    for para in doc.paragraphs:
        if para.text.strip():
            lines.append(para.text.strip())
    for table in doc.tables:
        for row in table.rows:
            row_cells = [c.text.strip() for c in row.cells]
            lines.append(" ".join(row_cells))
    return "\n".join(lines), {}


# ─── 파서: XLSX ─────────────────────────────────────────────────────────────

def _extract_xlsx(data: bytes) -> tuple[str, dict]:
    import io
    import openpyxl
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:
        return "", {}
    lines: list[str] = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None and str(c).strip()]
            if cells:
                lines.append(" ".join(cells))
    return "\n".join(lines), {}


# ─── 파서: PDF ──────────────────────────────────────────────────────────────

def _extract_pdf(data: bytes) -> tuple[str, dict]:
    try:
        import pdfplumber, io
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages_text = []
            for page in pdf.pages[:5]:  # 첫 5페이지만
                t = page.extract_text() or ""
                if t.strip():
                    pages_text.append(t)
            return "\n".join(pages_text), {}
    except Exception:
        pass
    # fallback: PyMuPDF
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=data, filetype="pdf")
        pages_text = []
        for i, page in enumerate(doc):
            if i >= 5:
                break
            pages_text.append(page.get_text())
        return "\n".join(pages_text), {}
    except Exception:
        return "", {}


# ─── 파서: 이미지 (JPG / PNG) ────────────────────────────────────────────────

def _extract_image(data: bytes, suffix: str) -> tuple[str, dict]:
    try:
        import pytesseract
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(data))
        # 한국어+영어 OCR
        text = pytesseract.image_to_string(img, lang="kor+eng")
        return text, {"ocr": True}
    except Exception as e:
        logger.warning("ocr_failed", error=str(e))
        return "", {}


# ─── 공개 인터페이스 ─────────────────────────────────────────────────────────

def extract_vendor_info(filename: str, data: bytes) -> ExtractResult:
    """파일 내용에서 업체 기본정보를 추출한다."""
    ext = Path(filename).suffix.lower()
    parser_name = "unknown"

    if ext == ".docx":
        text, _ = _extract_docx(data)
        parser_name = "docx"
    elif ext == ".xlsx":
        text, _ = _extract_xlsx(data)
        parser_name = "xlsx"
    elif ext == ".pdf":
        text, _ = _extract_pdf(data)
        parser_name = "pdf"
    elif ext in {".jpg", ".jpeg", ".png"}:
        text, _ = _extract_image(data, ext)
        parser_name = "image_ocr"
    else:
        text = ""
        parser_name = "unsupported"

    fields = _extract_from_text(text)
    confidence = fields.pop("_confidence", {})

    logger.info(
        "vendor_info_extracted",
        parser=parser_name,
        filename=filename,
        found={k: v is not None for k, v in fields.items()},
    )

    return ExtractResult(
        vendor_name=fields.get("vendor_name"),
        business_number=fields.get("business_number"),
        contact=fields.get("contact"),
        source=parser_name,
        confidence=confidence,
    )
