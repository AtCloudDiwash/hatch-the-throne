"""Sales tax."""
from decimal import ROUND_HALF_UP, Decimal

REGION_RATES = {"NONE": Decimal("0"), "MS": Decimal("0.07"), "LA": Decimal("0.0445"), "TX": Decimal("0.0625"), "CA": Decimal("0.0725")}
EXEMPT_TIERS = {"government"}


def tax_rate(region: str) -> Decimal:
    if region not in REGION_RATES:
        raise ValueError(f"unknown region {region}")
    return REGION_RATES[region]


def compute_tax(subtotal: Decimal, region: str, tier: str = "standard") -> Decimal:
    if tier in EXEMPT_TIERS:
        return Decimal("0.00")
    return (Decimal(str(subtotal)) * tax_rate(region)).quantize(Decimal("0.01"), ROUND_HALF_UP)
