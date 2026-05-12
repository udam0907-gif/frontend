import datetime
import random

import pytest

from app.services.business_date_util import (
    _ensure_business_day,
    calc_comparative_quote_date,
    calc_expense_resolution_date,
    calc_quote_date,
    parse_date,
)


def test_business_day_weekday_passthrough():
    d = datetime.date(2026, 5, 11)
    assert _ensure_business_day(d).weekday() < 5
    assert _ensure_business_day(d) == d


def test_business_day_saturday_to_friday():
    d = datetime.date(2026, 5, 9)
    assert _ensure_business_day(d) == datetime.date(2026, 5, 8)


def test_business_day_sunday_to_friday():
    d = datetime.date(2026, 5, 10)
    assert _ensure_business_day(d) == datetime.date(2026, 5, 8)


def test_quote_date_always_weekday_friday_issue():
    random.seed(1)
    issue = datetime.date(2026, 5, 15)
    for _ in range(20):
        q = calc_quote_date(issue, min_days_before=5, max_days_before=7)
        assert q.weekday() < 5
        delta = (issue - q).days
        assert 5 <= delta <= 8


def test_quote_date_always_weekday_monday_issue():
    random.seed(7)
    issue = datetime.date(2026, 5, 18)
    for _ in range(20):
        q = calc_quote_date(issue, min_days_before=5, max_days_before=7)
        assert q.weekday() < 5
        delta = (issue - q).days
        # 월요일 발행 + -7 -> 두 주 전 월요일, 사이에 주말 있으면 buffer 적용으로 금요일까지 밀림
        assert 5 <= delta <= 11


def test_comparative_differs_from_quote():
    issue = datetime.date(2026, 5, 15)
    quote = datetime.date(2026, 5, 8)
    comp = calc_comparative_quote_date(issue, quote)
    assert comp != quote
    assert comp.weekday() < 5


def test_expense_resolution_date_range():
    random.seed(3)
    issue = datetime.date(2026, 5, 15)
    for _ in range(20):
        er = calc_expense_resolution_date(issue, min_days_before=2, max_days_before=3)
        assert er.weekday() < 5
        delta = (issue - er).days
        assert 2 <= delta <= 4


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("2026-05-15", datetime.date(2026, 5, 15)),
        ("2026.05.15", datetime.date(2026, 5, 15)),
        ("2026/05/15", datetime.date(2026, 5, 15)),
        ("20260515", datetime.date(2026, 5, 15)),
        ("  2026-05-15  ", datetime.date(2026, 5, 15)),
        ("", None),
        (None, None),
        ("not-a-date", None),
    ],
)
def test_parse_date_variants(raw, expected):
    assert parse_date(raw) == expected


def test_parse_date_passthrough():
    d = datetime.date(2026, 5, 15)
    assert parse_date(d) == d
