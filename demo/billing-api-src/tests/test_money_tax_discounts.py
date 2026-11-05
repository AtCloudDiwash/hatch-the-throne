from decimal import Decimal as D

import pytest

from billing import discounts, money, tax


def test_to_money_and_sum():
    assert money.to_money("1.005") == D("1.01")
    assert money.sum_money([D("1.10"), "2.20"]) == D("3.30")


def test_format_money():
    assert money.format_money(D("1234.5")) == "$1,234.50"
    assert money.format_money(D("-2"), "EUR") == "-€2.00"


def test_split_evenly_sums_exactly():
    parts = money.split_evenly(D("10.00"), 3)
    assert parts == [D("3.34"), D("3.33"), D("3.33")] and sum(parts) == D("10.00")
    with pytest.raises(ValueError):
        money.split_evenly(D("1"), 0)


def test_compute_tax():
    assert tax.compute_tax(D("100.00"), "MS") == D("7.00")
    assert tax.compute_tax(D("100.00"), "NONE") == D("0.00")
    assert tax.compute_tax(D("100.00"), "MS", "government") == D("0.00")
    with pytest.raises(ValueError):
        tax.tax_rate("ZZ")


def test_volume_discount_bands():
    assert discounts.volume_discount(D("500.00")) == D("0.00")
    assert discounts.volume_discount(D("2000.00")) == D("20.00")
    assert discounts.volume_discount(D("20000.00"), "premier") == D("1200.00")


def test_early_pay_discount():
    assert discounts.early_pay_discount(D("100"), D("0.01"), "2026-02-01", "2026-01-10") == D("1.00")
    assert discounts.early_pay_discount(D("100"), D("0.01"), "2026-02-01", "2026-01-30") == D("0.00")
