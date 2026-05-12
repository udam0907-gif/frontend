"""세금계산서 발행일 기준 견적서/지출결의서 자동 날짜 계산."""
from __future__ import annotations

import datetime
import random
from typing import Optional


def _ensure_business_day(d: datetime.date) -> datetime.date:
    """주말이면 과거 방향으로 이동해서 평일 반환."""
    while d.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    return d


def _weekend_count_between(start: datetime.date, end: datetime.date) -> int:
    count = 0
    cursor = start
    while cursor < end:
        cursor += datetime.timedelta(days=1)
        if cursor.weekday() >= 5:
            count += 1
    return count


def calc_quote_date(
    issue_date: datetime.date,
    *,
    min_days_before: int = 5,
    max_days_before: int = 7,
    weekend_buffer: int = 1,
) -> datetime.date:
    """견적서 날짜 — 발행일 -5~-7일, 평일 보정.
    주말 끼면 weekend_buffer만큼 앞으로 더 이동."""
    days = random.randint(min_days_before, max_days_before)
    base = _ensure_business_day(issue_date - datetime.timedelta(days=days))
    if _weekend_count_between(base, issue_date) > 0:
        base = _ensure_business_day(base - datetime.timedelta(days=weekend_buffer))
    return base


def calc_comparative_quote_date(
    issue_date: datetime.date,
    quote_date: datetime.date,
) -> datetime.date:
    """비교견적서 날짜 — 견적서 하루 전 평일."""
    candidate = quote_date - datetime.timedelta(days=1)
    return _ensure_business_day(candidate)


def calc_expense_resolution_date(
    issue_date: datetime.date,
    *,
    min_days_before: int = 2,
    max_days_before: int = 3,
    weekend_buffer: int = 1,
) -> datetime.date:
    """지출결의서 날짜 — 발행일 -2~-3일, 평일 보정."""
    days = random.randint(min_days_before, max_days_before)
    base = _ensure_business_day(issue_date - datetime.timedelta(days=days))
    if _weekend_count_between(base, issue_date) > 0:
        base = _ensure_business_day(base - datetime.timedelta(days=weekend_buffer))
    return base


def parse_date(value: str | datetime.date | None) -> Optional[datetime.date]:
    """문자열/date를 date로 통합."""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    s = str(value).strip().replace(".", "-").replace("/", "-").replace(" ", "")
    if not s:
        return None
    for fmt, length in (("%Y-%m-%d", 10), ("%Y%m%d", 8)):
        try:
            return datetime.datetime.strptime(s[:length], fmt).date()
        except ValueError:
            continue
    return None
