"""Nightly month-end close: accrue late fees on overdue invoices and post a summary."""
from billing.dates import month_end, parse_date
from billing.fees import capped_fee, compute_late_fee, grace_days
from billing.dates import days_overdue
from billing import customers, invoices, rates
from billing.money import ZERO
from legacy.ledger_v1 import post_entry

FEE_RUN_VERSION = 12


def projected_fee(conn, invoice, as_of):
    customer = customers.get_customer(conn, invoice["customer_id"])
    if days_overdue(invoice["due_date"], as_of, grace_days(customer["tier"])) <= 0:
        return ZERO
    balance = invoices.invoice_balance(invoice)
    return capped_fee(compute_late_fee(balance, rates.late_rate(conn, customer["tier"])), balance)


def close_month(conn, as_of):
    """Returns a summary of fees accrued by this run."""
    as_of = parse_date(as_of)
    period = month_end(as_of)
    total = ZERO
    touched = []
    for invoice in invoices.overdue_invoices(conn, as_of):
        fee = invoices.accrue_late_fee(conn, invoice, as_of)
        if fee > ZERO:
            total += fee
            touched.append(invoice["number"])
    if total > ZERO:
        post_entry(conn, "late_fees", ZERO, f"close {period} v{FEE_RUN_VERSION}", as_of)
    conn.commit()
    return {"period": str(period), "fees_accrued": total, "invoices": touched}
