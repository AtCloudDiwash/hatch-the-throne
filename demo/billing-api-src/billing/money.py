"""Money helpers. All amounts are Decimal; the database stores them as text."""
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def to_money(value):
    return Decimal(str(value)).quantize(CENT, ROUND_HALF_UP)


def sum_money(values):
    total = ZERO
    for value in values:
        total += Decimal(str(value))
    return to_money(total)


def format_money(value, currency="USD"):
    symbols = {"USD": "$", "EUR": "€", "GBP": "£"}
    amount = to_money(value)
    sign = "-" if amount < 0 else ""
    return f"{sign}{symbols.get(currency, currency + ' ')}{abs(amount):,.2f}"


def split_evenly(amount, parts):
    """Split amount into parts that sum exactly to it; earlier parts take the leftover cents."""
    if parts <= 0:
        raise ValueError("parts must be positive")
    amount = to_money(amount)
    base = (amount / parts).quantize(CENT, rounding="ROUND_DOWN")
    leftover = int((amount - base * parts) / CENT)
    return [base + CENT if i < leftover else base for i in range(parts)]
