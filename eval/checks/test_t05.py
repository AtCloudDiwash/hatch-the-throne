from decimal import Decimal as D

from billing import invoices
from jobs.close_month import close_month, projected_fee
from reports.aging import aging_bucket

from conftest import line


def test_nightly_job_still_runs(conn, customer):
    inv = invoices.create_invoice(conn, customer["id"], line("40.20"), "2026-01-01")
    assert projected_fee(conn, inv, "2026-03-01") == D("1.01")
    assert close_month(conn, "2026-03-01")["fees_accrued"] == D("1.01")


def test_settlement_and_report_still_work(conn, customer, db_file):
    inv = invoices.create_invoice(conn, customer["id"], line("40.20"), "2026-01-01")
    assert aging_bucket(inv["id"], "2026-03-01", db_file)["projected_fee"] == D("1.01")
    assert invoices.settle_invoice(conn, inv["id"], as_of="2026-03-01")["late_fee"] == D("1.01")
