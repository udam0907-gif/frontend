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
        "business_registration",
    ),
    "fax": (
        "quote_template",
        "transaction_statement_template",
        "business_registration",
    ),
    "email": (
        "quote_template",
        "transaction_statement_template",
    ),
}

# 소스별 "해당 소스만 사용했을 때 비워야 할 필드" — DB 잔재 방지용
_SOURCE_EXCLUSIVE_FIELDS: dict[str, tuple[str, ...]] = {
    "business_registration": ("phone", "fax", "email"),
    "quote_template": ("company_registration_number", "representative_name", "business_type", "business_item"),
    "transaction_statement_template": ("company_registration_number", "representative_name", "business_type", "business_item"),
}


# OCR/PDF에서 자주 나오는 비표준 문자들을 정규화하기 위한 매핑
_DASH_CHARS = "‐‑‒–—―−⁃‧ー－"
_DASH_TRANS = str.maketrans({c: "-" for c in _DASH_CHARS})
_FULLWIDTH_DIGITS_TRANS = str.maketrans("０１２３４５６７８９", "0123456789")
_FULLWIDTH_LETTERS_TRANS = str.maketrans(
    "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ",
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz",
)


def _normalize_unicode(text: str) -> str:
    """OCR/PDF 추출 텍스트의 비표준 유니코드 문자를 ASCII로 정규화한다.

    - 다양한 dash/hyphen 변형 → '-'
    - 전각 숫자/영문 → 반각
    - 전각 콜론 → ':'
    - 가운뎃점/중점 → '-' (사업자번호 구분자로 종종 등장)
    """
    if not text:
        return text
    text = text.translate(_DASH_TRANS)
    text = text.translate(_FULLWIDTH_DIGITS_TRANS)
    text = text.translate(_FULLWIDTH_LETTERS_TRANS)
    text = text.replace("：", ":")
    text = text.replace("·", "-")
    text = text.replace("・", "-")
    return text


_KOR_OR_ENG_RE = re.compile(r"[A-Za-z가-힣]")
# 사업자번호: 다양한 구분자(공백/하이픈/점/슬래시) 및 다중 공백 허용
_BIZ_NUM_RE = re.compile(r"(?<!\d)(\d{3}\s*[-./]?\s*\d{2}\s*[-./]?\s*\d{5})(?!\d)")
_EMAIL_RE = re.compile(r"([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})", re.IGNORECASE)
# 전화/팩스: 0X(시외) 또는 1XXX(대표번호) 시작, 다양한 구분자 허용
_PHONE_RE = re.compile(
    r"(?<!\d)((?:0\d{1,3}|1\d{3})\s*[-./]?\s*\d{3,4}\s*[-./]?\s*\d{4})(?!\d)"
)
_ONLY_SYMBOL_RE = re.compile(r"^[^A-Za-z0-9가-힣]+$")
_PAREN_NUMBER_RE = re.compile(r"^\(?\d{1,6}\)?$")
_PAGE_NOISE_RE = re.compile(r"^(?:page|p\.?)\s*\d+$", re.IGNORECASE)
_ADDRESS_TRAIL_RE = re.compile(r"\s*\((?:[^()]{0,30})\)\s*$")

_LABEL_PATTERNS: dict[str, tuple[str, ...]] = {
    "company_name": (
        r"상호\s*\(\s*법인명\s*\)",
        r"상호",
        r"법인명",
        r"회사명",
        r"업체명",
        r"상호명",
        r"공급자",
        r"공급받는자",
    ),
    "company_registration_number": (
        r"사업자\s*등록\s*번호",
        r"등록번호",
        r"사업자번호",
    ),
    "representative_name": (
        r"대표자\s*성명",
        r"대표자명",
        r"대표자",
        r"성명",
    ),
    "address": (
        r"사업장\s*소재지",
        r"본점\s*소재지",
        r"소재지",
        r"주소",
    ),
    "business_type": (
        r"업태",
    ),
    "business_item": (
        r"종목",
        r"업종",
        r"사업의\s*종류",
    ),
    "phone": (
        r"전화\s*번호",
        r"휴대\s*전화",
        r"사업장\s*전화",
        r"연락처",
        r"전화",
        r"TEL\.?",
        r"Tel\.?",
        r"tel\.?",
        r"T\s*\.",
        r"☎",
    ),
    "fax": (
        r"팩스\s*번호",
        r"팩스",
        r"FAX\.?",
        r"Fax\.?",
        r"fax\.?",
        r"F\s*\.",
    ),
    "email": (
        r"전자우편주소",
        r"이메일",
        r"E-?mail",
        r"Email",
        r"e-?mail",
        r"메일",
    ),
}

_NEXT_LABEL_RE = re.compile(
    r"(?:상호\s*\(\s*법인명\s*\)|상호|법인명|회사명|업체명|상호명|공급자|공급받는자|"
    r"사업자\s*등록\s*번호|등록번호|사업자번호|"
    r"대표자\s*성명|대표자명|대표자|성명|"
    r"사업장\s*소재지|본점\s*소재지|소재지|주소|"
    r"업태|종목|업종|사업의\s*종류|"
    r"전화\s*번호|휴대\s*전화|사업장\s*전화|연락처|전화|TEL\.?|Tel\.?|tel\.?|"
    r"팩스\s*번호|팩스|FAX\.?|Fax\.?|fax\.?|"
    r"전자우편주소|이메일|E-?mail|Email|e-?mail|메일|"
    r"담당자\s*명|담당자\s*성명|담당자|기본\s*담당자|Manager)\s*[:：]"
)

_BUSINESS_REG_STOP_MARKERS = (
    "사업의종류",
    "발급사유",
    "공동사업자",
    "사업자단위과세적용사업자여부",
    "전자세금계산서전용전자우편주소",
)


class CompanyExtractResult(TypedDict):
    extracted: dict[str, str | None]
    source_by_field: dict[str, str]
    used_files: list[str]
    fields_to_clear: list[str]  # 이번 업로드에서 반드시 비워야 할 필드


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _normalize_text_block(text: str) -> str:
    text = _normalize_unicode(text)
    text = text.replace("\u3000", " ")
    text = re.sub(r"[|]+", " ", text)
    # OCR 테이블 구분자로 남는 대괄호를 공백으로 치환 (단어 경계 밖만)
    text = re.sub(r"(?<![\w가-힣])[\[\]](?![\w가-힣])", " ", text)
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
    # 대표번호(1588, 1544, 1577, 1899 등)
    if len(digits) == 8 and digits[0] == "1":
        return f"{digits[:4]}-{digits[4:]}"
    if digits.startswith("0504") and len(digits) == 11:
        return f"0504-{digits[4:7]}-{digits[7:]}"
    if digits.startswith("02") and len(digits) in (9, 10):
        return f"02-{digits[2:-4]}-{digits[-4:]}"
    if len(digits) == 11:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return raw.strip()


def _cleanup_value(field: str, value: str) -> str:
    cleaned = value.replace("|", " ").replace("\t", " ").strip(" :：,-")
    next_label = _NEXT_LABEL_RE.search(cleaned)
    if next_label:
        cleaned = cleaned[: next_label.start()].strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"^[\-_:./\s]+|[\-_:./\s]+$", "", cleaned)
    cleaned = re.sub(r"\b(?:page|p\.?)\s*\d+\b", "", cleaned, flags=re.IGNORECASE).strip()

    if field == "company_name":
        cleaned = re.sub(r"^[\[(]+|[\])]+$", "", cleaned).strip()
    elif field in {"business_type", "business_item"}:
        # OCR에서 자주 나오는 앞뒤 괄호/대괄호 제거 (예: "] 제조업" → "제조업")
        cleaned = re.sub(r"^[\[()\]\s]+|[\[()\]\s]+$", "", cleaned).strip()
    elif field == "company_registration_number":
        cleaned = _normalize_biz_num(cleaned)
    elif field in {"phone", "fax"}:
        cleaned = _normalize_phone(cleaned)
    elif field == "email":
        m = _EMAIL_RE.search(cleaned)
        cleaned = m.group(1) if m else cleaned
    elif field == "address":
        cleaned = _ADDRESS_TRAIL_RE.sub("", cleaned).strip()

    return cleaned.strip()


def _looks_like_noise(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return True
    if _ONLY_SYMBOL_RE.fullmatch(stripped):
        return True
    if _PAREN_NUMBER_RE.fullmatch(stripped):
        return True
    if re.fullmatch(r"[\d\s().,-]+", stripped):
        return True
    if stripped.startswith("(") and stripped.endswith(")") and len(stripped) <= 8:
        return True
    return False


def _is_plausible_value(field: str, value: str) -> bool:
    if not value:
        return False

    # 숫자/구분자만으로 구성된 필드(사업자번호·전화·팩스)는 _looks_like_noise를 우회한다.
    # _looks_like_noise는 "[\d\s().,-]+" 패턴을 노이즈로 분류하므로 이 필드들에 적용하면 안 됨.
    if field == "company_registration_number":
        return bool(re.fullmatch(r"\d{3}-\d{2}-\d{5}", value))

    if field in {"phone", "fax"}:
        normalized = re.sub(r"\D", "", value)
        if len(normalized) in (8, 9, 10, 11):
            if len(normalized) == 8 and normalized[0] == "1":
                return True  # 1588/1544 등 대표번호
            if len(normalized) >= 9 and normalized[0] == "0":
                return True
        return bool(_PHONE_RE.fullmatch(value))

    if _looks_like_noise(value):
        return False

    if field == "company_name":
        stripped = value.strip()
        if len(stripped) < 2 or len(stripped) > 80:
            return False
        if _BIZ_NUM_RE.fullmatch(stripped):
            return False
        if not _KOR_OR_ENG_RE.search(stripped):
            return False
        if any(token in stripped for token in ("등록번호", "사업장소재지", "사업의종류", "발급사유")):
            return False
        return True

    if field == "representative_name":
        stripped = value.strip()
        if len(stripped) < 2 or len(stripped) > 30:
            return False
        if any(ch.isdigit() for ch in stripped):
            return False
        if any(token in stripped for token in ("사업장", "소재지", "등록번호", "개업연월일")):
            return False
        return bool(_KOR_OR_ENG_RE.search(stripped))

    if field == "address":
        stripped = value.strip()
        if len(stripped) < 8 or len(stripped) > 200:
            return False
        if not _KOR_OR_ENG_RE.search(stripped):
            return False
        return any(token in stripped for token in ("시", "군", "구", "로", "길", "동", "읍", "면", "리"))

    if field == "business_type":
        stripped = value.strip()
        if len(stripped) < 2 or len(stripped) > 60:
            return False
        if any(token in stripped for token in ("사업의종류", "발급사유", "공동사업자", "전자세금계산서")):
            return False
        return bool(_KOR_OR_ENG_RE.search(stripped))

    if field == "business_item":
        stripped = value.strip()
        if len(stripped) < 2 or len(stripped) > 120:
            return False
        if any(token in stripped for token in ("사업의종류", "발급사유", "공동사업자", "전자세금계산서")):
            return False
        return bool(_KOR_OR_ENG_RE.search(stripped))

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


def _extract_biz_text_block(compact_text: str, start_label: str, stop_labels: tuple[str, ...]) -> str | None:
    start = compact_text.find(start_label)
    if start == -1:
        return None
    start += len(start_label)
    while start < len(compact_text) and compact_text[start] in ":：":
        start += 1

    end = len(compact_text)
    for label in stop_labels:
        idx = compact_text.find(label, start)
        if idx != -1 and idx < end:
            end = idx

    candidate = compact_text[start:end].strip()
    return candidate or None


def _extract_compact_labeled_value(
    compact_text: str,
    labels: tuple[str, ...],
    stop_labels: tuple[str, ...],
) -> str | None:
    for label in labels:
        candidate = _extract_biz_text_block(compact_text, label, stop_labels)
        if candidate:
            return candidate
    return None


def _collect_following_lines(lines: list[str], start_index: int, max_lines: int = 6) -> list[str]:
    collected: list[str] = []
    for line in lines[start_index + 1 : start_index + 1 + max_lines]:
        compact = _compact_text(line)
        if any(marker in compact for marker in _BUSINESS_REG_STOP_MARKERS):
            break
        if ":" in line or "：" in line:
            break
        collected.append(line)
    return collected


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _normalize_business_registration_lines(text: str) -> list[str]:
    normalized_text = _normalize_text_block(text)
    raw_lines = [line for line in normalized_text.split("\n") if line]
    normalized_lines: list[str] = []
    i = 0
    while i < len(raw_lines):
        current = raw_lines[i]
        compact = _compact_text(current)
        next_line = raw_lines[i + 1] if i + 1 < len(raw_lines) else None
        next_compact = _compact_text(next_line) if next_line else ""
        third_line = raw_lines[i + 2] if i + 2 < len(raw_lines) else None
        third_compact = _compact_text(third_line) if third_line else ""

        if compact == "상" and next_compact == "호":
            merged = "상호"
            if third_compact.startswith(":"):
                merged += third_line
                i += 3
            else:
                i += 2
            normalized_lines.append(merged)
            continue

        if compact == "성" and next_compact == "명":
            merged = "성명"
            if third_compact.startswith(":"):
                merged += third_line
                i += 3
            else:
                i += 2
            normalized_lines.append(merged)
            continue

        normalized_lines.append(current)
        i += 1

    return normalized_lines


def _extract_business_registration_fields(text: str) -> dict[str, str | None]:
    extracted: dict[str, str | None] = {field: None for field in AUTO_EXTRACT_FIELDS}
    lines = _normalize_business_registration_lines(text)
    normalized_text = "\n".join(lines)
    compact_text = _compact_text(normalized_text)

    biz_num_match = _BIZ_NUM_RE.search(normalized_text)
    if biz_num_match:
        candidate = _normalize_biz_num(biz_num_match.group(1))
        if _is_plausible_value("company_registration_number", candidate):
            extracted["company_registration_number"] = candidate

    # 패턴이 못 잡은 경우(OCR 노이즈/줄바꿈 등): "등록번호" 라벨 근처에서 10자리 숫자 강제 수집
    if not extracted["company_registration_number"]:
        candidate = _extract_compact_labeled_value(
            compact_text,
            ("사업자등록번호", "등록번호", "사업자번호"),
            ("상호", "법인명", "성명", "대표자", "생년월일", "개업연월일", "사업장소재지"),
        )
        if candidate:
            digits_only = re.sub(r"\D", "", candidate)
            if len(digits_only) >= 10:
                normalized = _normalize_biz_num(digits_only[:10])
                if _is_plausible_value("company_registration_number", normalized):
                    extracted["company_registration_number"] = normalized

    company_name_block = _extract_biz_text_block(
        compact_text,
        "상호",
        ("성명", "대표자", "생년월일", "개업연월일", "사업장소재지"),
    )
    if company_name_block:
        candidate = _cleanup_value("company_name", company_name_block)
        if _is_plausible_value("company_name", candidate):
            extracted["company_name"] = candidate

    representative_block = _extract_biz_text_block(
        compact_text,
        "성명",
        ("생년월일", "주민등록번호", "개업연월일", "사업장소재지"),
    ) or _extract_biz_text_block(
        compact_text,
        "대표자",
        ("생년월일", "주민등록번호", "개업연월일", "사업장소재지"),
    )
    if representative_block:
        candidate = _cleanup_value("representative_name", representative_block)
        if _is_plausible_value("representative_name", candidate):
            extracted["representative_name"] = candidate

    address_block = _extract_biz_text_block(
        compact_text,
        "사업장소재지",
        ("사업의종류", "발급사유", "공동사업자", "전자세금계산서전용전자우편주소"),
    )
    if address_block:
        candidate = _cleanup_value("address", address_block)
        if _is_plausible_value("address", candidate):
            extracted["address"] = candidate

    for idx, line in enumerate(lines):
        compact_line = _compact_text(line)

        if not extracted["business_type"] and "업태" in compact_line:
            parts = line.split("업태", 1)
            head_value = _cleanup_value("business_type", parts[1] if len(parts) > 1 else "")
            candidates = [head_value] if head_value else []
            candidates.extend(_collect_following_lines(lines, idx))
            valid = [item for item in _dedupe_keep_order([_cleanup_value("business_type", item) for item in candidates]) if _is_plausible_value("business_type", item)]
            if valid:
                extracted["business_type"] = valid[0]

        if not extracted["business_item"] and ("종목" in compact_line or "업종" in compact_line):
            split_key = "종목" if "종목" in compact_line else "업종"
            parts = line.split(split_key, 1)
            head_value = _cleanup_value("business_item", parts[1] if len(parts) > 1 else "")
            candidates = [head_value] if head_value else []
            candidates.extend(_collect_following_lines(lines, idx))
            valid = [item for item in _dedupe_keep_order([_cleanup_value("business_item", item) for item in candidates]) if _is_plausible_value("business_item", item)]
            if valid:
                extracted["business_item"] = valid[0]

        if not extracted["email"] and "전자세금계산서전용전자우편주소" in compact_line:
            parts = line.split("전자세금계산서전용전자우편주소", 1)
            candidate = _cleanup_value("email", parts[1] if len(parts) > 1 else "")
            if candidate and _is_plausible_value("email", candidate):
                extracted["email"] = candidate

    return extracted


def _extract_company_fields(text: str, source: str) -> dict[str, str | None]:
    extracted: dict[str, str | None] = {field: None for field in AUTO_EXTRACT_FIELDS}
    normalized_text = _normalize_text_block(text)
    compact_text = _compact_text(normalized_text)

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

    if source in {"quote_template", "transaction_statement_template"}:
        if not extracted["phone"]:
            candidate = _extract_compact_labeled_value(
                compact_text,
                ("전화번호", "연락처", "TEL", "Tel"),
                ("이메일", "팩스", "담당자", "공급자", "사업자번호", "대표자", "상호", "주소"),
            )
            if candidate:
                candidate = _normalize_phone(candidate)
                if _is_plausible_value("phone", candidate):
                    extracted["phone"] = candidate

        if not extracted["fax"]:
            candidate = _extract_compact_labeled_value(
                compact_text,
                ("팩스", "팩스번호", "FAX", "Fax"),
                ("이메일", "담당자", "연락처", "전화번호", "공급자", "사업자번호", "대표자", "상호", "주소"),
            )
            if candidate:
                candidate = _normalize_phone(candidate)
                if _is_plausible_value("fax", candidate):
                    extracted["fax"] = candidate

        if not extracted["email"]:
            candidate = _extract_compact_labeled_value(
                compact_text,
                ("이메일", "전자우편주소", "E-mail", "Email", "메일"),
                ("팩스", "담당자", "연락처", "전화번호", "공급자", "사업자번호", "대표자", "상호", "주소"),
            )
            if candidate:
                candidate = _cleanup_value("email", candidate)
                if _is_plausible_value("email", candidate):
                    extracted["email"] = candidate

    # 사업자등록증에서는 전화/팩스 전체 텍스트 검색을 실행하지 않음 (오탐 방지)
    if not extracted["phone"] and source != "business_registration":
        match = _PHONE_RE.search(normalized_text)
        if match:
            candidate = _normalize_phone(match.group(1))
            if _is_plausible_value("phone", candidate):
                extracted["phone"] = candidate

    if source in {"quote_template", "transaction_statement_template"}:
        for field in ("company_registration_number", "representative_name", "business_type", "business_item"):
            extracted[field] = None

    if source == "business_registration":
        # 사업자등록증에서 전화/팩스/이메일은 추출하지 않음 (오탐 방지)
        # 해당 정보는 견적서/거래명세서 양식에서만 추출
        extracted["phone"] = None
        extracted["fax"] = None
        extracted["email"] = None

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

    # 소스별 전용 필드 중 이번 추출에서 값이 없는 것은 DB에서도 비움
    fields_to_clear: list[str] = []
    for _src in used_files:
        for _field in _SOURCE_EXCLUSIVE_FIELDS.get(_src, ()):
            if not merged.get(_field) and _field not in fields_to_clear:
                fields_to_clear.append(_field)

    return CompanyExtractResult(
        extracted=merged,
        source_by_field=source_by_field,
        used_files=used_files,
        fields_to_clear=fields_to_clear,
    )
