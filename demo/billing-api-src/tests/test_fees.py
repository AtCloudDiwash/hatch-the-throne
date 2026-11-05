from decimal import Decimal as D

from billing import fees


def test_late_fee_simple_percentage():
    assert fees.compute_late_fee(D("100.00"), D("0.05")) == D("5.00")


def test_late_fee_typical_balance():
    assert fees.compute_late_fee(D("250.00"), D("0.015")) == D("3.75")


def test_late_fee_rounds_to_cents():
    assert fees.compute_late_fee(D("19.99"), D("0.02")) == D("0.40")


def test_no_fee_on_zero_balance():
    assert fees.compute_late_fee(D("0.00"), D("0.05")) == D("0.00")


def test_grace_days_by_tier():
    assert fees.grace_days("standard") == 0
    assert fees.grace_days("premier") == 15


def test_late_rate_by_tier():
    assert fees.late_rate_for("premier") == D("0.015")
    assert fees.late_rate_for("standard") == D("0.025")


def test_cap_limits_fee():
    assert fees.capped_fee(D("50.00"), D("100.00")) == D("10.00")
    assert fees.capped_fee(D("5.00"), D("100.00")) == D("5.00")


def test_fee_not_due_inside_grace():
    assert fees.fee_for_balance(D("100"), D("0.05"), "2026-01-01", "2026-01-10", "premier") == D("0.00")
    assert fees.fee_for_balance(D("100"), D("0.05"), "2026-01-01", "2026-02-10", "premier") == D("5.00")
