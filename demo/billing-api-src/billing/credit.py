"""Credit notes."""
import datetime as dt
from decimal import Decimal

from billing.dates import parse_date
from billing.invoices import InvalidInvoiceState, get_invoice, invoice_balance
from billing.money import ZERO, sum_money, to_money
from legacy.ledger_v1 import post_entry


def issue_credit_note(conn, invoice_id, amount, reason, issued_on=None):
    amount = to_money(amount)
    if amount <= ZERO:
        raise ValueError("credit must be positive")
    invoice = get_invoice(conn, invoice_id)
    if invoice["status"] == "void":
        raise InvalidInvoiceState("void")
    if amount > invoice_balance(invoice):
        raise ValueError("credit exceeds the balance")
    issued = parse_date(issued_on or dt.date.today())
    cur = conn.execute("INSERT INTO credit_notes(invoice_id, amount, reason, issued_on) VALUES (?,?,?,?)",
                       (invoice_id, str(amount), reason, str(issued)))
    conn.execute("UPDATE invoices SET paid = ? WHERE id = ?", (str(invoice["paid"] + amount), invoice_id))
    post_entry(conn, "credits", amount, f"credit {invoice['number']}", issued, invoice["legacy_ref"])
    post_entry(conn, "receivables", -amount, f"credit {invoice['number']}", issued, invoice["legacy_ref"])
    conn.commit()
    return {"id": cur.lastrowid, "invoice_id": invoice_id, "amount": amount, "reason": reason, "issued_on": str(issued)}


def credits_for_invoice(conn, invoice_id):
    return [{**dict(r), "amount": Decimal(r["amount"])}
            for r in conn.execute("SELECT * FROM credit_notes WHERE invoice_id = ? ORDER BY id", (invoice_id,))]


def credit_total(conn, invoice_id):
    return sum_money(c["amount"] for c in credits_for_invoice(conn, invoice_id))
