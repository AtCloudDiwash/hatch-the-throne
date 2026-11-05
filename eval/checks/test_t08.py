from decimal import Decimal as D

import pytest

from billing import invoices
from reports.aging import aging_bucket, aging_report, bucket_name

from conftest import line


@pytest.mark.parametrize("days,name", [(0, "current"), (1, "1-30"), (30, "1-30"), (31, "31-60"), (60, "31-60"), (61, "61-90"), (90, "61-90"), (91, "90+")])
def test_bucket_boundaries(days, name):
    assert bucket_name(days) == name


def test_report_totals(conn, customer, db_file):
    invoices.create_invoice(conn, customer["id"], line("100.00"), "2026-01-01")
    invoices.create_invoice(conn, customer["id"], line("50.00"), "2026-02-20")
    totals = aging_report("2026-03-15", db_file)
    assert totals["31-60"] == D("100.00") and totals["1-30"] == D("0.00") and totals["current"] == D("50.00")
    assert set(totals) == {"current", "1-30", "31-60", "61-90", "90+"}


def test_no_projected_fee_when_already_charged(conn, customer, db_file):
    inv = invoices.create_invoice(conn, customer["id"], line("100.00"), "2026-01-01")
    invoices.accrue_late_fee(conn, inv, "2026-03-01")
    conn.commit()
    assert aging_bucket(inv["id"], "2026-03-02", db_file)["projected_fee"] == D("0.00")
