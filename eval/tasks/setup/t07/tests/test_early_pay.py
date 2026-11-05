from decimal import Decimal as D

from billing.discounts import early_pay_discount


def test_exactly_ten_days_early_earns_discount():
    assert early_pay_discount(D("100"), D("0.01"), "2026-02-01", "2026-01-22") == D("1.00")


def test_nine_days_early_earns_nothing():
    assert early_pay_discount(D("100"), D("0.01"), "2026-02-01", "2026-01-23") == D("0.00")
