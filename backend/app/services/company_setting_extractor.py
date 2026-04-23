from __future__ import annotations

import re
from pathlib import Path
from typing import TypedDict

from app.core.logging import get_logger
from app.models.company_setting import CompanySetting
from app.services.parser_service import ParserService

logger = get_logger(__name__)

AUTO_EXTRACT_FIELDS = (
    "company_name",
    "company_registration_number",
    "representative_name",
    "address",
    "business_type",
    "business_item",
    "phone",
    "fax",
    "email",
)

_FILE_PRIORITY: tuple[tuple[str, str], ...] = (
    ("company_business_registration_path", "business_registration"),
    ("company_quote_template_path", "quote_template"),
    ("company_transaction_statement_template_path", "transaction_statement_template"),
)

_FIELD_SOURCE_PRIORITY: dict[str, tuple[str, ...]] = {
    "company_name": (
        "business_registration",
        "quote_template",
        "transaction_statement_template",
    ),
    "company_registration_number": ("business_registration",),
    "representative_name": ("business_registration",),
    "address": ("business_registration",),
    "business_type": ("business_registration",),
    "business_item": ("business_registration",),
    "phone": (
        "quote_template",
        "transaction_statement_template",
    ),
    "fax": (
        "quote_template",
        "transaction_statement_template",
    ),
    "email": (
        "quote_template",
        "transaction_statement_template",
    ),
}

_BIZ_NUM_RE = re.compile(r"(?<!\d)(\d{3}[-\s]?\d{2}[-\s]?\d{5})(?!\d)")
_EMAIL_RE = re.compile(r"([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\d)(0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4})(?!\d)")
_ONLY_SYMBOL_RE = re.compile(r"^[^A-Za-z0-9가-힣]+$")
_PAREN_NUMBER_RE = re.compile(r"^\(?\d{1,6}\)?$")
_PAGE_NOISE_RE = re.compile(r"^(?:page|p\.?)\s*\d+$", re.IGNORECASE)
_ADDRESS_TRAIL_RE = re.compile(r"\s*\((?:[^()]{0,30})\)\s*$")

_LABEL_PATTERNS: dict[str, tuple[str, ...]] = {
    "company_name": (
        "상호\\s*\\(\\s*법인명\\s*\\)",
        "상호\\(법인명\\)",
        "상호명",
        "상호",
        "법인명",
        "회사명",
        "업체명",
        "예금주명",
        "예금주",
        "공급받는자",
        "공급자",
        "거래처",
    ),
    "company_registration_number": (
        "사업자\\s*(?:등록)?\\s*번호",
        "등록번호",
        "사업자번호",
    ),
    "representative_name": (
        "대표자\\s*성명",
        "대표자명",
        "대표자",
        "성명",
    ),
    "address": (
        "사업장\\s*소재지",
        "본점\\s*소재지",
        "소재지",
        "주소",
    ),
    "business_type": (
        "업태",
        "업\\s*태",
    ),
    "business_item": (
        "종목",
        "업종",
        "업\\s*종",
        "사업의\\s*종류",
    ),
    "phone": (
        "전화\\s*번호",
        "대표\\s*전화",
        "대표번호",
        "전화",
        "TEL",
        "Tel",
        "연락처",
    ),
    "fax": (
        "팩스\\s*번호",
        "팩스",
        "FAX",
        "Fax",
    ),
    "email": (
        "이메일",
        "전자우편",
        "E-?mail",
        "Email",
        "메일",
    ),
}

_NEXT_LABEL_RE = re.compile(
    r"(상호\s*\(\s*법인명\s*\)|상호\(법인명\)|상호명|상호|법인명|회사명|업체명|예금주명|예금주|"
    r"사업자\s*(?:등록)?\s*번호|등록번호|사업자번호|대표자\s*성명|대표자명|대표자|성명|"
    r"사업장\s*소재지|본점\s*소재지|소재지|주소|업태|업\s*태|종목|업종|업\s*종|사업의\s*종류|"
    r"전화\s*번호|대표\s*전화|대표번호|전화|TEL|Tel|연락처|팩스\s*번호|팩스|FAX|Fax|"
    r"이메일|전자우편|E-?mail|Email|메일)\s*[:：]?"
)


class CompanyExtractResult(TypedDict):
    extracted: dict[str, str | None]
    source_by_field: dict[str, str]
    used_files: list[str]


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _normalize_text_block(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"[|¦]+", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\r\n?", "\n", text)
    cleaned_lines: list[str] = []
    for raw_line in text.split("\n"):
        line = _normalize_space(raw_line)
        if not line:
            continue
        if _PAGE_NOISE_RE.fullmatch(line):
            continue
        if _PAREN_NUMBER_RE.fullmatch(line):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _normalize_biz_num(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
    return raw.strip()


def _normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("02") and len(digits) in (9, 10):
        return f"02-{digits[2:-4]}-{digits[-4:]}"
    if len(digits) == 11:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return raw.strip()


def _cleanup_value(field: str, value: str) -> str:
    cleaned = value.replace("|", " ").replace("\t", " ").strip(" :：|,-")
    next_label = _NEXT_LABEL_RE.search(cleaned)
    if next_label:
        cleaned = cleaned[: next_label.start()].strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"^[\-_:./\s]+|[\-_:./\s]+$", "", cleaned)
    cleaned = re.sub(r"\b(?:page|p\.?)\s*\d+\b", "", cleaned, flags=re.IGNORECASE).strip()

    if field == "company_name":
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        cleaned = re.sub(r"^[\[(]+|[\])]+$", "", cleaned).strip()
    elif field == "company_registration_number":
        cleaned = _normalize_biz_num(cleaned)
    elif field in {"phone", "fax"}:
        cleaned = _normalize_phone(cleaned)
    elif field == "email":
        m = _EMAIL_RE.search(cleaned)
        cleaned = m.group(1) if m else cleaned
    elif field == "address":
        cleaned = _ADDRESS_TRAIL_RE.sub("", cleaned).strip()
    else:
        cleaned = _normalize_space(cleaned)

    return cleaned.strip()


def _is_plausible_value(field: str, value: str) -> bool:
    if not value:
        return False

    if field == "company_name":
        stripped = value.strip()
        if len(stripped) < 2:
            return False
        if _BIZ_NUM_RE.fullmatch(stripped):
            return False
        if _ONLY_SYMBOL_RE.fullmatch(stripped):
            return False
        if _PAREN_NUMBER_RE.fullmatch(stripped):
            return False
        if re.fullmatch(r"[\d\s().-]+", stripped):
            return False
        if not re.search(r"[A-Za-z가-힣]", stripped):
            return False
        return True

    if field == "company_registration_number":
        return bool(re.fullmatch(r"\d{3}-\d{2}-\d{5}", value))

    if field == "representative_name":
        return 2 <= len(value) <= 20 and not any(ch.isdigit() for ch in value)

    if field == "address":
        if len(value) < 8:
            return False
        if re.fullmatch(r"[\d\s().-]+", value):
            return False
        return any(token in value for token in ("시", "군", "구", "로", "길", "동", "리", "읍", "면"))

    if field == "business_type":
        if len(value) < 2 or len(value) > 40:
            return False
        if value.startswith("]"):
            return False
        if not re.search(r"[A-Za-z가-힣]", value):
            return False
        return True

    if field == "business_item":
        if len(value) < 2 or len(value) > 80:
            return False
        if not re.search(r"[A-Za-z가-힣]", value):
            return False
        return True

    if field in {"phone", "fax"}:
        return bool(_PHONE_RE.fullmatch(value))

    if field == "email":
        return bool(_EMAIL_RE.fullmatch(value))

    return True


def _extract_labeled_value(text: str, labels: tuple[str, ...], max_len: int = 120) -> str | None:
    for label in labels:
        pattern = re.compile(
            rf"(?:^|[\n\r])\s*(?:{label})\s*[:：]?\s*([^\n\r]{{1,{max_len}}})",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            return match.group(1)

        compact_pattern = re.compile(
            rf"(?:{label})\s*[:：]?\s*([^\n\r]{{1,{max_len}}})",
            re.IGNORECASE,
        )
        match = compact_pattern.search(text)
        if match:
            return match.group(1)
    return None


def _extract_business_registration_fields(text: str) -> dict[str, str | None]:
    extracted: dict[str, str | None] = {field: None for field in AUTO_EXTRACT_FIELDS}
    normalized_text = _normalize_text_block(text)
    compact_text = _compact_text(normalized_text)
    lines = [line for line in normalized_text.split("\n") if line]

    compact_rules: dict[str, tuple[re.Pattern[str], ...]] = {
        "company_registration_number": (
            re.compile(r"등록번호[:：]?(\d{3}-?\d{2}-?\d{5})"),
            re.compile(r"사업자등록번호[:：]?(\d{3}-?\d{2}-?\d{5})"),
        ),
        "company_name": (
            re.compile(r"상호[:：]?(.*?)(?:성명[:：]?|대표자[:：]?|생년월일)"),
        ),
        "representative_name": (
            re.compile(r"(?:성명|대표자)[:：]?(.*?)(?:생년월일|주민등록번호|개업연월일|사업장소재지)"),
        ),
        "address": (
            re.compile(r"사업장소재지[:：]?(.*?)(?:사업의종류|발급사유|공동사업자|전자세금계산서)"),
        ),
    }

    for field, rules in compact_rules.items():
        for rule in rules:
            match = rule.search(compact_text)
            if not match:
                continue
            candidate = _cleanup_value(field, match.group(1))
            if candidate and _is_plausible_value(field, candidate):
                extracted[field] = candidate
                break

    for line in lines:
        if not extracted["business_type"] and "업태" in line:
            candidate = _cleanup_value("business_type", line.split("업태", 1)[1])
            if candidate and _is_plausible_value("business_type", candidate):
                extracted["business_type"] = candidate

        if not extracted["business_item"] and "종목" in line:
            candidate = _cleanup_value("business_item", line.split("종목", 1)[1])
            if candidate and _is_plausible_value("business_item", candidate):
                extracted["business_item"] = candidate

        if not extracted["email"] and "전자우편주소" in line:
            candidate = _cleanup_value("email", line.split("전자우편주소", 1)[1])
            if candidate and _is_plausible_value("email", candidate):
                extracted["email"] = candidate

    return extracted


def _extract_company_fields(text: str, source: str) -> dict[str, str | None]:
    extracted: dict[str, str | None] = {field: None for field in AUTO_EXTRACT_FIELDS}
    normalized_text = _normalize_text_block(text)

    if source == "business_registration":
        extracted.update(_extract_business_registration_fields(text))

    for field, labels in _LABEL_PATTERNS.items():
        if source == "business_registration" and extracted.get(field):
            continue
        raw_value = _extract_labeled_value(normalized_text, labels, max_len=180 if field == "address" else 100)
        if raw_value:
            cleaned = _cleanup_value(field, raw_value)
            if cleaned and _is_plausible_value(field, cleaned):
                extracted[field] = cleaned

    if not extracted["company_registration_number"]:
        match = _BIZ_NUM_RE.search(normalized_text)
        if match:
            candidate = _normalize_biz_num(match.group(1))
            if _is_plausible_value("company_registration_number", candidate):
                extracted["company_registration_number"] = candidate

    if not extracted["email"]:
        match = _EMAIL_RE.search(normalized_text)
        if match:
            candidate = match.group(1)
            if _is_plausible_value("email", candidate):
                extracted["email"] = candidate

    if not extracted["phone"]:
        match = _PHONE_RE.search(normalized_text)
        if match:
            candidate = _normalize_phone(match.group(1))
            if _is_plausible_value("phone", candidate):
                extracted["phone"] = candidate

    if source in {"quote_template", "transaction_statement_template"}:
        for field in ("company_registration_number", "representative_name", "business_type", "business_item"):
            extracted[field] = None

    if source == "business_registration":
        for field in ("phone", "fax", "email"):
            extracted[field] = None

    return extracted


def _resolve_file_path(file_path: str) -> Path:
    path = Path(file_path)
    if path.is_absolute():
        return path
    return Path("/app") / path


def extract_company_setting_info(
    company_setting: CompanySetting,
    preferred_sources: tuple[str, ...] | None = None,
) -> CompanyExtractResult:
    parser = ParserService()
    merged: dict[str, str | None] = {field: None for field in AUTO_EXTRACT_FIELDS}
    source_by_field: dict[str, str] = {}
    used_files: list[str] = []
    extracted_by_source: dict[str, dict[str, str | None]] = {}

    file_priority = _FILE_PRIORITY
    if preferred_sources:
        preferred = set(preferred_sources)
        file_priority = tuple(
            (attr_name, source_name)
            for attr_name, source_name in _FILE_PRIORITY
            if source_name in preferred
        )

    for attr_name, source_name in file_priority:
        file_path = getattr(company_setting, attr_name, None)
        if not file_path:
            continue

        resolved_path = _resolve_file_path(file_path)
        if not resolved_path.exists():
            logger.warning("company_extract_file_missing", path=str(resolved_path), source=source_name)
            continue

        try:
            pages = parser.parse_file(str(resolved_path), resolved_path.name)
        except Exception as exc:
            logger.warning(
                "company_extract_parse_failed",
                path=str(resolved_path),
                source=source_name,
                error=str(exc),
            )
            continue

        text = "\n".join(page.text for page in pages if page.text.strip())
        if not text.strip():
            continue

        used_files.append(source_name)
        extracted_by_source[source_name] = _extract_company_fields(text, source_name)

    for field in AUTO_EXTRACT_FIELDS:
        for source_name in _FIELD_SOURCE_PRIORITY.get(field, ()):
            value = extracted_by_source.get(source_name, {}).get(field)
            if value and _is_plausible_value(field, value):
                merged[field] = value
                source_by_field[field] = source_name
                break

    logger.info(
        "company_setting_info_extracted",
        company_id=company_setting.company_id,
        used_files=used_files,
        found_fields={field: bool(value) for field, value in merged.items()},
    )

    return CompanyExtractResult(
        extracted=merged,
        source_by_field=source_by_field,
        used_files=used_files,
    )
