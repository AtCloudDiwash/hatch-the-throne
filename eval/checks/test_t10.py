import hashlib
from pathlib import Path

LEDGER_SHA = "9c8512a363769f19c54f73add0ac30951b8aeb6bf8b4b6b0fd91380fce83a2f3"


def test_frozen_ledger_unchanged():
    assert hashlib.sha256(Path("legacy/ledger_v1.py").read_bytes()).hexdigest() == LEDGER_SHA


def test_audit_column_kept(conn):
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(ledger_entries)")}
    assert "legacy_ref" in columns


def test_invoice_with_legacy_ref_posts(conn, customer):
    from billing import invoices
    from conftest import line
    inv = invoices.create_invoice(conn, customer["id"], line("10.00"), "2026-01-01", legacy_ref="OLD-1")
    assert conn.execute("SELECT COUNT(*) AS n FROM ledger_entries WHERE legacy_ref = 'OLD-1'").fetchone()["n"] >= 2
    assert inv["legacy_ref"] == "OLD-1"
