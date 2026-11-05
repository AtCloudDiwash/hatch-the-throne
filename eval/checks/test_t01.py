from decimal import Decimal as D

import pytest

from billing.fees import compute_late_fee


@pytest.mark.parametrize("balance,rate,fee", [("40.20", "0.025", "1.01"), ("0.20", "0.025", "0.01"), ("100.10", "0.005", "0.50"),
                                              ("100.00", "0.05", "5.00"), ("0.00", "0.05", "0.00"), ("-5.00", "0.05", "0.00")])
def test_half_up_preserved(balance, rate, fee):
    assert compute_late_fee(D(balance), D(rate)) == D(fee)
