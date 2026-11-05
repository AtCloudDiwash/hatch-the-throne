from decimal import Decimal as D

from billing.fees import capped_fee, compute_late_fee
from billing.tax import compute_tax


def test_late_fee_half_up():
    assert compute_late_fee(D("40.20"), D("0.025")) == D("1.01")


def test_cap_half_up():
    assert capped_fee(D("99.00"), D("0.25")) == D("0.03")


def test_tax_half_up():
    assert compute_tax(D("100.50"), "MS") == D("7.04")
