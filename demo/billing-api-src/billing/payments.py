"""Partial payments and refunds."""
import datetime as dt

from billing.dates import parse_date
from billing.invoices import InvalidInvoiceState, get_invoice, invoice_balance
from billing.money import ZERO, sum_money, to_money
from legacy.ledger_v1 import post_entry

METHODS = ("card", "ach", "check", "wire")


class Overpayment(Exception):
    pass


def record_payment(conn, invoice_id, amount, method="card", received_on=None):
    if method not in METHODS:
        raise ValueError(f"unknown payment method {method}")
    amount = to_money(amount)
    if amount <= ZERO:
        raise ValueError("payment must be positive")
    invoice = get_invoice(conn, invoice_id)
    if invoice["status"] != "open":
        raise InvalidInvoiceState(invoice["status"])
    balance = invoice_balance(invoice)
    if amount > balance:
        raise Overpayment(f"{amount} exceeds the balance {balance}")
    received = parse_date(received_on or dt.date.today())
    conn.execute("INSERT INTO payments(invoice_id, amount, method, received_on) VALUES (?,?,?,?)",
                 (invoice_id, str(amount), method, str(received)))
    status = "paid" if amount == balance else "open"
    conn.execute("UPDATE invoices SET paid = ?, status = ? WHERE id = ?", (str(invoice["paid"] + amount), status, invoice_id))
    post_entry(conn, "cash", amount, f"payment {invoice['number']}", received, invoice["legacy_ref"])
    post_entry(conn, "receivables", -amount, f"payment {invoice['number']}", received, invoice["legacy_ref"])
    conn.commit()
    return get_invoice(conn, invoice_id)


def payments_for_invoice(conn, invoice_id):
    return [dict(r) for r in conn.execute("SELECT * FROM payments WHERE invoice_id = ? ORDER BY id", (invoice_id,))]


def total_received(conn, invoice_id):
    return sum_money(p["amount"] for p in payments_for_invoice(conn, invoice_id))


def refund_payment(conn, payment_id, as_of=None):
    row = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
    if row is None:
        raise KeyError(payment_id)
    invoice = get_invoice(conn, row["invoice_id"])
    amount = to_money(row["amount"])
    as_of = parse_date(as_of or dt.date.today())
    conn.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
    conn.execute("UPDATE invoices SET paid = ?, status = 'open' WHERE id = ?", (str(invoice["paid"] - amount), invoice["id"]))
    post_entry(conn, "cash", -amount, f"refund {invoice['number']}", as_of, invoice["legacy_ref"])
    post_entry(conn, "receivables", amount, f"refund {invoice['number']}", as_of, invoice["legacy_ref"])
    conn.commit()
    return get_invoice(conn, invoice["id"])
