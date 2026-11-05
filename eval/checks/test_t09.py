from decimal import Decimal as D

from billing import fees, invoices, rates

from conftest import line


def test_new_rate_everywhere(conn, customer):
    assert fees.DEFAULT_LATE_RATE == D("0.03")
    assert rates.late_rate(conn) == D("0.03"), "db/rates.sql must change too; it is what settlement reads"
    inv = invoices.create_invoice(conn, customer["id"], line("100.00"), "2026-01-01")
    assert invoices.settle_invoice(conn, inv["id"], as_of="2026-03-01")["late_fee"] == D("3.00")


def test_premier_rate_untouched(conn):
    assert rates.late_rate(conn, "premier") == D("0.015")
