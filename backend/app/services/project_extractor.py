"""project_extractor.py
Claude LLM 기반 PDF 추출 서비스 (regex fallback 포함).

Supported doc_type values:
  - "auto"        : 문서 종류 자동 감지 (권장)
  - "plan"        : 사업계획서
  - "agreement"   : 협약체결확약서
  - "researcher"  : 참여연구원현황표
"""
from __future__ import annotations

import io
import json
import re
from decimal import Decimal, InvalidOperation
from typing import TypedDict

from app.core.logging import get_logger
from app.models.enums import CategoryType

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 반환 타입
# ---------------------------------------------------------------------------

class ExtractedResearcher(TypedDict):
    personnel_type: str
    name: str
    position: str | None
    annual_salary: Decimal | None
    monthly_salary: Decimal | None
    participation_months: int | None
    participation_rate: Decimal | None
    cash_amount: Decimal | None
    in_kind_amount: Decimal | None
    sort_order: int


class ExtractedBudgetCategory(TypedDict):
    category_type: str
    allocated_amount: Decimal


class ExtractedProjectData(TypedDict):
    name: str | None
    code: str | None
    institution: str | None
    principal_investigator: str | None
    period_start: str | None
    period_end: str | None
    total_budget: Decimal | None
    budget_categories: list[ExtractedBudgetCategory]
    researchers: list[ExtractedResearcher]
    # 사업계획서 추가 항목
    overview: str | None                # 개요
    deliverables: str | None            # 결과물 및 주요 성능지표
    schedule: str | None                # 사업추진·기술개발 일정
    doc_type: str
    confidence: float


# ---------------------------------------------------------------------------
# PDF 텍스트/테이블 추출
# ---------------------------------------------------------------------------

def _extract_pdf_text(file_bytes: bytes) -> str:
    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = [page.get_text("text") for page in doc]
        doc.close()
        return "\n".join(pages)
    except Exception as e:
        logger.warning("fitz_extract_failed", error=str(e))
        return ""


def _extract_pdf_tables(file_bytes: bytes) -> list[list[list[str]]]:
    try:
        import pdfplumber
        tables = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_tables = page.extract_tables()
                if page_tables:
                    tables.extend(page_tables)
        return tables
    except Exception as e:
        logger.warning("pdfplumber_extract_failed", error=str(e))
        return []


def _tables_to_text(tables: list[list[list[str]]]) -> str:
    """테이블을 LLM이 읽기 쉬운 텍스트 표로 변환한다."""
    parts = []
    for t_idx, table in enumerate(tables):
        rows = []
        for row in table:
            cells = [str(c).strip().replace("\n", " ") if c else "" for c in row]
            rows.append(" | ".join(cells))
        parts.append(f"[표 {t_idx+1}]\n" + "\n".join(rows))
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# 문서 종류 자동 감지 (간단 키워드 — LLM 호출 전 빠른 판단)
# ---------------------------------------------------------------------------

_PLAN_KEYWORDS = [
    "창업아이템명", "창업팀", "사업화", "초기창업", "창업패키지", "사업계획서",
    "창업아이디어", "아이템명", "창업목표",
]
_AGREEMENT_KEYWORDS = [
    "협약체결", "확약서", "협약서", "과제번호", "협약기간", "선정사업명", "협약금액",
]
_RESEARCHER_KEYWORDS = [
    "참여연구원현황", "인력현황표", "참여연구원 현황", "인건비현황",
    "연구원현황표", "참여인력현황",
]


def _detect_doc_type(text: str) -> str:
    t = text[:3000]  # 앞부분만 빠르게 검사
    plan_score  = sum(1 for kw in _PLAN_KEYWORDS       if kw in t)
    agree_score = sum(1 for kw in _AGREEMENT_KEYWORDS  if kw in t)
    res_score   = sum(1 for kw in _RESEARCHER_KEYWORDS if kw in t)

    best = max(plan_score, agree_score, res_score)
    if best == 0:
        return "plan"  # 기본값
    if plan_score == best:
        return "plan"
    if agree_score == best:
        return "agreement"
    return "researcher"


# ---------------------------------------------------------------------------
# LLM 기반 추출 (메인 경로)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
당신은 한국 R&D 사업 문서(사업계획서, 협약서, 연구개발계획서 등)에서 구조화 정보를 추출하는 전문가입니다.
주어진 PDF 텍스트와 표에서 정보를 추출하여 반드시 유효한 JSON만 반환하세요.
추출할 수 없는 필드는 null로 처리하세요. JSON 외 다른 텍스트는 절대 출력하지 마세요.
"""

_USER_PROMPT_TEMPLATE = """\
## 문서 종류 힌트: {doc_type_hint}

## PDF 텍스트
{text}

## 테이블 (표)
{tables}

---
위 내용을 분석하여 다음 JSON 형식으로 추출하세요:

{{
  "doc_type": "plan | agreement | researcher",
  "name": "과제명 또는 창업아이템명 또는 연구개발과제명",
  "code": "과제번호 또는 협약번호 (숫자·영문 코드, 없으면 null)",
  "institution": "주관기관명 또는 신청기업명 또는 수행기관명",
  "principal_investigator": "연구책임자 또는 대표자 성명 (한글 이름만)",
  "period_start": "YYYY-MM-DD",
  "period_end": "YYYY-MM-DD",
  "total_budget": 총사업비_원단위_숫자,
  "budget_categories": [
    {{"category_type": "labor|materials|outsourcing|test_report|meeting|other", "allocated_amount": 원단위_숫자}}
  ],
  "researchers": [
    {{
      "personnel_type": "기존 또는 신규",
      "name": "성명",
      "position": "직위 또는 직급",
      "annual_salary": 숫자_또는_null,
      "monthly_salary": 숫자_또는_null,
      "participation_months": 숫자_또는_null,
      "participation_rate": 숫자_퍼센트_또는_null,
      "cash_amount": 숫자_또는_null,
      "in_kind_amount": 숫자_또는_null
    }}
  ],
  "overview": "사업 개요 또는 아이템 개요 (핵심 내용 300자 이내 요약, 없으면 null)",
  "deliverables": "결과물 및 주요 성능지표 내용 요약 (없으면 null)",
  "schedule": "사업추진 일정 또는 기술개발 일정 요약 (없으면 null)"
}}

【날짜 추출 규칙 — 반드시 준수】
- 출력 형식: 반드시 YYYY-MM-DD
- '2026년 4월 1일' → '2026-04-01'
- '26.04.01' 또는 '26.4.1' → '2026-04-01'
- '2026.04 ~ 2027.03' → start: '2026-04-01', end: '2027-03-31'
- '사업기간: 협약일로부터 12개월' → 협약일 기준으로 계산 불가 시 null
- '24년 4월' → '2024-04-01'
- 범위(~, -, ∼) 왼쪽이 시작일, 오른쪽이 종료일
- '지원기간', '수행기간', '연구기간', '협약기간' 모두 사업기간으로 처리

【금액 추출 규칙】
- 원 단위 숫자만 출력
- '1억 6천만원' → 160000000
- '7,200만원' → 72000000
- '천원 단위' 표기인 경우 × 1000 변환
- '72,000 (천원)' → 72000000

【비목 매핑】
- 인건비, 연구원인건비 → labor
- 재료비, 연구재료비 → materials
- 외주용역비, 외주비, 위탁연구비 → outsourcing
- 시험검사비, 시험·검사비, 분석비 → test_report
- 회의비, 국내출장비, 행사비, 세미나 → meeting
- 특허, 지식재산권, 광고선전비, 수수료, 기타경비, 간접비 → other
"""


async def _extract_with_llm(
    text: str,
    tables: list[list[list[str]]],
    doc_type_hint: str,
) -> ExtractedProjectData | None:
    """Claude API로 PDF에서 정보를 추출한다."""
    from app.services.llm_service import get_llm_service

    llm = get_llm_service()

    # 텍스트 길이 제한 (토큰 절약)
    max_text = 12000
    text_snippet = text[:max_text] + ("…(이하 생략)" if len(text) > max_text else "")

    # 테이블 텍스트 (최대 4000자)
    tables_text = _tables_to_text(tables)[:4000] or "(표 없음)"

    doc_type_labels = {
        "plan": "사업계획서",
        "agreement": "협약체결확약서",
        "researcher": "참여연구원현황표",
    }
    hint_label = doc_type_labels.get(doc_type_hint, "사업계획서")

    user_message = _USER_PROMPT_TEMPLATE.format(
        doc_type_hint=hint_label,
        text=text_snippet,
        tables=tables_text,
    )

    try:
        response = await llm.complete(
            system_prompt=_SYSTEM_PROMPT,
            user_message=user_message,
            prompt_version="project_extractor_v1",
            cache_system=True,
        )
        raw_json = response.content.strip()

        # JSON 코드블록 제거
        raw_json = re.sub(r"^```(?:json)?\s*", "", raw_json, flags=re.MULTILINE)
        raw_json = re.sub(r"\s*```$", "", raw_json, flags=re.MULTILINE)
        raw_json = raw_json.strip()

        data = json.loads(raw_json)
        return _parse_llm_response(data, doc_type_hint)

    except json.JSONDecodeError as e:
        logger.error("llm_json_parse_error", error=str(e))
        return None
    except Exception as e:
        logger.error("llm_extract_error", error=str(e))
        return None


def _parse_llm_response(data: dict, doc_type_hint: str) -> ExtractedProjectData:
    """LLM JSON 응답을 ExtractedProjectData로 변환한다."""

    def to_decimal(v: object) -> Decimal | None:
        if v is None:
            return None
        try:
            return Decimal(str(v).replace(",", "").replace(" ", ""))
        except (InvalidOperation, ValueError):
            return None

    def to_int(v: object) -> int | None:
        if v is None:
            return None
        try:
            return int(float(str(v).replace(",", "")))
        except (ValueError, TypeError):
            return None

    # doc_type
    doc_type = str(data.get("doc_type") or doc_type_hint)
    if doc_type not in ("plan", "agreement", "researcher"):
        doc_type = doc_type_hint

    # budget_categories
    raw_cats = data.get("budget_categories") or []
    budget_categories: list[ExtractedBudgetCategory] = []
    seen_cats: set[str] = set()
    valid_cats = {c.value for c in CategoryType}
    for cat in raw_cats:
        if not isinstance(cat, dict):
            continue
        ct = str(cat.get("category_type") or "")
        if ct not in valid_cats or ct in seen_cats:
            continue
        amt = to_decimal(cat.get("allocated_amount"))
        if amt and amt > 0:
            budget_categories.append({"category_type": ct, "allocated_amount": amt})
            seen_cats.add(ct)

    # researchers
    raw_res = data.get("researchers") or []
    researchers: list[ExtractedResearcher] = []
    for idx, r in enumerate(raw_res):
        if not isinstance(r, dict):
            continue
        name = str(r.get("name") or "").strip()
        if not name:
            continue
        pt = str(r.get("personnel_type") or "기존")
        if pt not in ("기존", "신규"):
            pt = "기존"
        researchers.append(ExtractedResearcher(
            personnel_type=pt,
            name=name[:100],
            position=str(r.get("position") or "").strip() or None,
            annual_salary=to_decimal(r.get("annual_salary")),
            monthly_salary=to_decimal(r.get("monthly_salary")),
            participation_months=to_int(r.get("participation_months")),
            participation_rate=to_decimal(r.get("participation_rate")),
            cash_amount=to_decimal(r.get("cash_amount")),
            in_kind_amount=to_decimal(r.get("in_kind_amount")),
            sort_order=idx,
        ))

    # total_budget
    total_budget = to_decimal(data.get("total_budget"))

    # 날짜 정규화
    def clean_date(v: object) -> str | None:
        s = str(v or "").strip()
        if not s or s == "null":
            return None
        # 이미 YYYY-MM-DD 형식이면 그대로
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            return s
        # 숫자만 있는 경우 (YYYYMMDD)
        if re.match(r"^\d{8}$", s):
            return f"{s[:4]}-{s[4:6]}-{s[6:]}"
        return s  # 형식 불명 → 그대로 반환, 프론트에서 표시

    period_start = clean_date(data.get("period_start"))
    period_end   = clean_date(data.get("period_end"))

    # 추가 텍스트 필드
    def clean_text(v: object) -> str | None:
        s = str(v or "").strip()
        return s if s and s != "null" else None

    overview     = clean_text(data.get("overview"))
    deliverables = clean_text(data.get("deliverables"))
    schedule     = clean_text(data.get("schedule"))

    # 신뢰도 계산
    key_fields = {
        "plan":       [data.get("name"), period_start, period_end, total_budget],
        "agreement":  [data.get("name"), data.get("code"), data.get("institution"), period_start],
        "researcher": [researchers],
    }
    fields = key_fields.get(doc_type, [data.get("name"), total_budget])
    filled = sum(1 for f in fields if f not in (None, [], "", "null"))
    confidence = round(filled / max(len(fields), 1), 2)

    return ExtractedProjectData(
        name=str(data.get("name") or "").strip() or None,
        code=str(data.get("code") or "").strip() or None,
        institution=str(data.get("institution") or "").strip() or None,
        principal_investigator=str(data.get("principal_investigator") or "").strip() or None,
        period_start=period_start,
        period_end=period_end,
        total_budget=total_budget,
        budget_categories=budget_categories,
        researchers=researchers,
        overview=overview,
        deliverables=deliverables,
        schedule=schedule,
        doc_type=doc_type,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Regex Fallback (LLM 실패 시)
# ---------------------------------------------------------------------------

_COMMA_NUM_RE = re.compile(r"[\d,]+")

def _parse_number(text: str | None) -> Decimal | None:
    if not text:
        return None
    m = _COMMA_NUM_RE.search(str(text).replace(" ", ""))
    if not m:
        return None
    try:
        return Decimal(m.group().replace(",", ""))
    except InvalidOperation:
        return None

_PERIOD_RANGE_RE = re.compile(
    r"(20\d{2}|\d{2})[.\-/년](\d{1,2})[.\-/월]?(\d{0,2})[일]?"
    r"\s*[~\-～]\s*"
    r"(20\d{2}|\d{2})[.\-/년](\d{1,2})[.\-/월]?(\d{0,2})[일]?"
)

def _to_iso(year_str: str, month_str: str, day_str: str) -> str:
    y = int(year_str)
    if y < 100:
        y += 2000
    return f"{y:04d}-{int(month_str):02d}-{int(day_str) if day_str else 1:02d}"

def _parse_period_range(text: str) -> tuple[str | None, str | None]:
    m = _PERIOD_RANGE_RE.search(text)
    if m:
        g = m.groups()
        return _to_iso(g[0], g[1], g[2] or "01"), _to_iso(g[3], g[4], g[5] or "28")
    return None, None

_CATEGORY_KEYWORD_MAP: list[tuple[list[str], str]] = [
    (["인건비"],                          CategoryType.labor.value),
    (["재료비"],                          CategoryType.materials.value),
    (["외주용역비", "외주비", "용역비"],   CategoryType.outsourcing.value),
    (["시험", "검사", "분석비"],          CategoryType.test_report.value),
    (["회의비", "출장비"],                CategoryType.meeting.value),
    (["특허", "광고", "수수료", "기타"],  CategoryType.other.value),
]

def _map_category(raw: str) -> str | None:
    cleaned = raw.strip().replace(" ", "")
    for keywords, cat in _CATEGORY_KEYWORD_MAP:
        if any(kw.replace(" ", "") in cleaned for kw in keywords):
            return cat
    return None

_BUDGET_LINE_RE = re.compile(
    r"(인건비|재료비|외주용역비|외주비|시험[·]?검사|회의비|출장비|특허|광고|수수료|기타경비|기타)"
    r".*?([\d,]{3,})"
)

_NAME_PATS = [
    re.compile(r"창업\s*아이템\s*명\s*[:：]?\s*(.+)"),
    re.compile(r"(?:과제|사업)\s*명\s*[:：]?\s*(.+)"),
]
_CODE_PATS = [
    re.compile(r"과제\s*번호\s*[:：]?\s*([A-Za-z0-9\-]+)"),
    re.compile(r"(?<!\d)(\d{8,12})(?!\d)"),
]
_INST_PATS = [
    re.compile(r"(?:주관|신청)\s*기관\s*[:：]?\s*(.{2,40})"),
    re.compile(r"기업명\s*[:：]?\s*(.{2,40})"),
]
_PI_PATS = [
    re.compile(r"(?:연구|사업)\s*책임자\s*[:：]?\s*([가-힣]{2,6})"),
    re.compile(r"대표자\s*[:：]?\s*([가-힣]{2,6})"),
]
_PERIOD_PATS = [
    re.compile(r"(?:사업|연구|협약)\s*기간\s*[:：]?\s*(.{5,40})"),
]
_BUDGET_PATS = [
    re.compile(r"총\s*사업비\s*[:：]?\s*([\d,]+)"),
    re.compile(r"총\s*(?:연구비|예산)\s*[:：]?\s*([\d,]+)"),
]


def _extract_regex_fallback(text: str, tables: list[list[list[str]]], doc_type: str) -> ExtractedProjectData:
    """Regex 기반 fallback 추출."""
    lines = text.splitlines()
    result: dict = dict(name=None, code=None, institution=None, principal_investigator=None,
                        period_start=None, period_end=None, total_budget=None,
                        budget_categories=[], researchers=[])

    def first_match(pats: list[re.Pattern], in_lines: list[str]) -> str | None:
        for pat in pats:
            for line in in_lines:
                m = pat.search(line)
                if m:
                    return m.group(1).strip()
        return None

    result["name"] = first_match(_NAME_PATS, lines)
    result["code"] = first_match(_CODE_PATS, lines[:30])
    result["institution"] = first_match(_INST_PATS, lines)
    result["principal_investigator"] = first_match(_PI_PATS, lines)

    for pat in _PERIOD_PATS:
        for line in lines:
            m = pat.search(line)
            if m:
                s, e = _parse_period_range(m.group(1))
                if s and e:
                    result["period_start"], result["period_end"] = s, e
                    break
        if result["period_start"]:
            break

    for pat in _BUDGET_PATS:
        for line in lines:
            m = pat.search(line)
            if m:
                v = _parse_number(m.group(1))
                if v and v > 0:
                    result["total_budget"] = v
                    break
        if result["total_budget"]:
            break

    # 비목
    seen: set[str] = set()
    for line in lines:
        m = _BUDGET_LINE_RE.search(line)
        if m:
            cat = _map_category(m.group(1))
            if cat and cat not in seen:
                amt = _parse_number(m.group(2))
                if amt and amt > 0:
                    result["budget_categories"].append({"category_type": cat, "allocated_amount": amt})
                    seen.add(cat)

    confidence = _calc_confidence(result, doc_type)
    return ExtractedProjectData(
        **result,
        overview=None,
        deliverables=None,
        schedule=None,
        doc_type=doc_type,
        confidence=confidence,
    )


def _calc_confidence(result: dict, doc_type: str) -> float:
    key_fields = {
        "plan":       ["name", "period_start", "period_end", "total_budget", "budget_categories"],
        "agreement":  ["name", "code", "institution", "principal_investigator", "period_start"],
        "researcher": ["researchers"],
    }
    fields = key_fields.get(doc_type, ["name", "total_budget"])
    filled = sum(1 for f in fields if result.get(f) not in (None, [], {}, ""))
    return round(filled / max(len(fields), 1), 2)


# ---------------------------------------------------------------------------
# 공개 API (async)
# ---------------------------------------------------------------------------

async def extract_project_data(
    file_bytes: bytes,
    filename: str,
    doc_type: str = "auto",
) -> ExtractedProjectData:
    """
    Parameters
    ----------
    file_bytes : PDF 파일 바이트
    filename   : 원본 파일명
    doc_type   : "auto" | "plan" | "agreement" | "researcher"

    Returns
    -------
    ExtractedProjectData
    """
    logger.info("project_extract_start", filename=filename, doc_type=doc_type, size=len(file_bytes))

    # 1. PDF 파싱
    text   = _extract_pdf_text(file_bytes)
    tables = _extract_pdf_tables(file_bytes)

    # 2. 문서 종류 자동 감지
    if doc_type == "auto" or not doc_type:
        doc_type = _detect_doc_type(text)
        logger.info("doc_type_auto_detected", doc_type=doc_type)

    # 3. LLM 추출 (메인)
    result = await _extract_with_llm(text, tables, doc_type)

    # 4. LLM 실패 시 regex fallback
    if result is None:
        logger.warning("llm_extract_failed_using_regex", filename=filename)
        result = _extract_regex_fallback(text, tables, doc_type)

    logger.info(
        "project_extract_done",
        filename=filename, doc_type=result["doc_type"],
        confidence=result["confidence"],
        name=result["name"], code=result["code"],
        researcher_count=len(result["researchers"]),
        budget_count=len(result["budget_categories"]),
    )
    return result
