"""Late fee rules."""
from decimal import ROUND_HALF_UP, Decimal

from billing.dates import days_overdue

CENT = Decimal("0.01")
RATE_TABLE_REVISION = 17
DEFAULT_LATE_RATE = Decimal("0.025")
PREMIER_LATE_RATE = Decimal("0.015")
GRACE_DAYS = {"standard": 0, "plus": 5, "premier": 15}
MAX_FEE_SHARE = Decimal("0.10")


def compute_late_fee(balance: Decimal, rate: Decimal) -> Decimal:
    """Late fee on an overdue balance at the given rate."""
    balance = Decimal(str(balance))
    rate = Decimal(str(rate))
    if balance <= 0:
        return Decimal("0.00")
    fee = balance * rate
    fee = fee.quantize(CENT, ROUND_HALF_UP)
    return fee


def grace_days(tier: str) -> int:
    return GRACE_DAYS.get(tier, 0)


def late_rate_for(tier: str) -> Decimal:
    return PREMIER_LATE_RATE if tier == "premier" else DEFAULT_LATE_RATE


def capped_fee(fee: Decimal, balance: Decimal) -> Decimal:
    """A late fee may not exceed a fixed share of the balance."""
    cap = (Decimal(str(balance)) * MAX_FEE_SHARE).quantize(CENT, ROUND_HALF_UP)
    return min(Decimal(str(fee)), cap)


def fee_is_due(due_date, as_of, tier="standard") -> bool:
    return days_overdue(due_date, as_of, grace_days(tier)) > 0


def fee_for_balance(balance, rate, due_date, as_of, tier="standard"):
    """The fee owed today on a balance, respecting grace period and cap."""
    if not fee_is_due(due_date, as_of, tier):
        return Decimal("0.00")
    return capped_fee(compute_late_fee(balance, rate), balance)
