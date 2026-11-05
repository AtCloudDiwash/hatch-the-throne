"""Volume and early-payment discounts."""
from decimal import ROUND_HALF_UP, Decimal

from billing.dates import days_overdue, parse_date

VOLUME_BANDS = [(Decimal("10000"), Decimal("0.05")), (Decimal("5000"), Decimal("0.03")), (Decimal("1000"), Decimal("0.01"))]
TIER_EXTRA = {"standard": Decimal("0"), "plus": Decimal("0.005"), "premier": Decimal("0.01")}


def volume_rate(subtotal: Decimal, tier: str = "standard") -> Decimal:
    subtotal = Decimal(str(subtotal))
    for floor, rate in VOLUME_BANDS:
        if subtotal >= floor:
            return rate + TIER_EXTRA.get(tier, Decimal("0"))
    return Decimal("0")


def volume_discount(subtotal: Decimal, tier: str = "standard") -> Decimal:
    return (Decimal(str(subtotal)) * volume_rate(subtotal, tier)).quantize(Decimal("0.01"), ROUND_HALF_UP)


def early_pay_discount(balance, rate, due_date, paid_on, window_days=10):
    """Discount for paying at least window_days before the due date."""
    if days_overdue(paid_on, due_date) < window_days or parse_date(paid_on) > parse_date(due_date):
        return Decimal("0.00")
    return (Decimal(str(balance)) * Decimal(str(rate))).quantize(Decimal("0.01"), ROUND_HALF_UP)
