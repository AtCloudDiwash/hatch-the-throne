"""Rate lookups from the rates table."""
from decimal import Decimal

from billing.fees import DEFAULT_LATE_RATE, PREMIER_LATE_RATE


def get_rate(conn, kind, default=None):
    row = conn.execute("SELECT value FROM rates WHERE kind = ?", (kind,)).fetchone()
    if row is None:
        if default is None:
            raise KeyError(kind)
        return default
    return Decimal(row["value"])


def late_rate(conn, tier="standard"):
    if tier == "premier":
        return get_rate(conn, "late_fee_premier", PREMIER_LATE_RATE)
    return get_rate(conn, "late_fee", DEFAULT_LATE_RATE)


def rate_revision(conn):
    row = conn.execute("SELECT MAX(revision) AS r FROM rates").fetchone()
    return row["r"]
