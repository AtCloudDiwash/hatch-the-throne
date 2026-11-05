"""Accounts-receivable aging report, used by the finance team each Monday."""
from decimal import Decimal

from billing import customers, db, invoices, rates
from billing.dates import days_overdue, parse_date
from billing.fees import compute_late_fee

BUCKETS = (("current", 0), ("1-30", 30), ("31-60", 60), ("61-90", 90))


def bucket_name(days):
    for name, ceiling in BUCKETS:
        if days <= ceiling:
            return name
    return "90+"


def aging_bucket(invoice_id, as_of, path=None):
    """Bucket and projected late fee for one invoice, read from the live database."""
    conn = db.connect(path)
    try:
        invoice = invoices.get_invoice(conn, invoice_id)
        customer = customers.get_customer(conn, invoice["customer_id"])
        days = days_overdue(invoice["due_date"], parse_date(as_of))
        balance = invoices.invoice_balance(invoice)
        fee = compute_late_fee(balance, rates.late_rate(conn, customer["tier"])) if days and not invoice["late_fee"] else Decimal("0.00")
        return {"bucket": bucket_name(days), "balance": balance, "projected_fee": fee}
    finally:
        conn.close()


def aging_report(as_of, path=None):
    conn = db.connect(path)
    try:
        ids = [i["id"] for i in invoices.list_invoices(conn, status="open")]
    finally:
        conn.close()
    totals = {name: Decimal("0.00") for name, _ in BUCKETS}
    totals["90+"] = Decimal("0.00")
    for invoice_id in ids:
        row = aging_bucket(invoice_id, as_of, path)
        totals[row["bucket"]] += row["balance"]
    return totals
