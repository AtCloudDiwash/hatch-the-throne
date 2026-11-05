import datetime as dt

from billing.dates import add_months


def test_clamps_to_month_end():
    assert add_months("2026-01-31", 1) == dt.date(2026, 2, 28)
    assert add_months("2028-01-31", 1) == dt.date(2028, 2, 29)
    assert add_months("2026-03-31", 1) == dt.date(2026, 4, 30)


def test_year_wrap_and_negative():
    assert add_months("2026-12-15", 1) == dt.date(2027, 1, 15)
    assert add_months("2026-01-15", -1) == dt.date(2025, 12, 15)
    assert add_months("2026-05-31", 12) == dt.date(2027, 5, 31)
