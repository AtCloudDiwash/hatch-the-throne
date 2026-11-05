import datetime as dt

from billing import dates


def test_add_days():
    assert dates.add_days("2026-01-30", 3) == dt.date(2026, 2, 2)


def test_add_months_mid_month():
    assert dates.add_months("2026-01-15", 1) == dt.date(2026, 2, 15)
    assert dates.add_months("2026-11-15", 3) == dt.date(2027, 2, 15)


def test_month_end():
    assert dates.month_end("2026-04-10") == dt.date(2026, 4, 30)


def test_days_overdue():
    assert dates.days_overdue("2026-01-01", "2026-01-11") == 10
    assert dates.days_overdue("2026-01-11", "2026-01-01") == 0
    assert dates.days_overdue("2026-01-01", "2026-01-11", grace=5) == 5


def test_business_days():
    assert dates.business_days_between("2026-11-02", "2026-11-09") == 5
    assert dates.next_business_day("2026-11-07") == dt.date(2026, 11, 9)


def test_quarter():
    assert dates.quarter_of("2026-02-01") == 1 and dates.quarter_of("2026-11-01") == 4
