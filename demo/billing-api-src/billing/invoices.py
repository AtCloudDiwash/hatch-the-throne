"""Invoice lifecycle: creation, balance, settlement, voiding."""
import datetime as dt
from decimal import Decimal

from billing import customers, events, numbering, rates
from billing.dates import add_days, parse_date
from billing.discounts import volume_discount
from billing.fees import compute_late_fee, capped_fee, fee_is_due
from billing.money import ZERO, sum_money, to_money
from billing.tax import compute_tax
from legacy.ledger_v1 import post_entry


class InvoiceNotFound(Exception):
    pass


class InvalidInvoiceState(Exception):
    pass


class PaymentTooSmall(Exception):
    pass


def _row_to_invoice(row):
    inv = dict(row)
    for key in ("subtotal", "discount", "tax", "late_fee", "paid"):
        inv[key] = Decimal(inv[key])
    return inv


def invoice_total(invoice):
    return to_money(invoice["subtotal"] - invoice["discount"] + invoice["tax"] + invoice["late_fee"])


def invoice_balance(invoice):
    return to_money(invoice_total(invoice) - invoice["paid"])


def line_amount(line):
    return to_money(Decimal(str(line["unit_price"])) * int(line["quantity"]))


def create_invoice(conn, customer_id, lines, issue_date=None, currency="USD", legacy_ref=None):
    if not lines:
        raise ValueError("an invoice needs at least one line")
    customer = customers.get_customer(conn, customer_id)
    issue = parse_date(issue_date or dt.date.today())
    subtotal = sum_money(line_amount(line) for line in lines)
    discount = volume_discount(subtotal, customer["tier"])
    tax = compute_tax(subtotal - discount, customer["region"], customer["tier"])
    number = numbering.next_invoice_number(conn, issue.year)
    due = add_days(issue, customer["payment_terms_days"])
    cur = conn.execute(
        "INSERT INTO invoices(customer_id, number, issue_date, due_date, subtotal, discount, tax, currency, legacy_ref)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (customer_id, number, str(issue), str(due), str(subtotal), str(discount), str(tax), currency, legacy_ref),
    )
    invoice_id = cur.lastrowid
    for line in lines:
        conn.execute("INSERT INTO invoice_lines(invoice_id, description, quantity, unit_price) VALUES (?,?,?,?)",
                     (invoice_id, line["description"], int(line["quantity"]), str(line["unit_price"])))
    post_entry(conn, "receivables", subtotal - discount + tax, f"invoice {number}", issue, legacy_ref)
    post_entry(conn, "revenue", -(subtotal - discount), f"invoice {number}", issue, legacy_ref)
    if tax:
        post_entry(conn, "tax_payable", -tax, f"invoice {number}", issue, legacy_ref)
    conn.commit()
    return get_invoice(conn, invoice_id)


def get_invoice(conn, invoice_id):
    row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if row is None:
        raise InvoiceNotFound(invoice_id)
    return _row_to_invoice(row)


def invoice_lines(conn, invoice_id):
    return [dict(r) for r in conn.execute("SELECT * FROM invoice_lines WHERE invoice_id = ? ORDER BY id", (invoice_id,))]


def list_invoices(conn, customer_id=None, status=None):
    sql, params = "SELECT * FROM invoices WHERE 1=1", []
    if customer_id is not None:
        sql += " AND customer_id = ?"
        params.append(customer_id)
    if status:
        sql += " AND status = ?"
        params.append(status)
    return [_row_to_invoice(r) for r in conn.execute(sql + " ORDER BY id", params)]


def overdue_invoices(conn, as_of):
    out = []
    for invoice in list_invoices(conn, status="open"):
        customer = customers.get_customer(conn, invoice["customer_id"])
        if fee_is_due(invoice["due_date"], as_of, customer["tier"]):
            out.append(invoice)
    return out


def accrue_late_fee(conn, invoice, as_of):
    """Add the late fee for an overdue invoice, once. Returns the fee added."""
    if invoice["late_fee"] > ZERO:
        return ZERO
    customer = customers.get_customer(conn, invoice["customer_id"])
    if not fee_is_due(invoice["due_date"], as_of, customer["tier"]):
        return ZERO
    balance = invoice_balance(invoice)
    fee = capped_fee(compute_late_fee(balance, rates.late_rate(conn, customer["tier"])), balance)
    if fee > ZERO:
        conn.execute("UPDATE invoices SET late_fee = ? WHERE id = ?", (str(fee), invoice["id"]))
        post_entry(conn, "receivables", fee, f"late fee {invoice['number']}", as_of, invoice["legacy_ref"])
        post_entry(conn, "late_fees", -fee, f"late fee {invoice['number']}", as_of, invoice["legacy_ref"])
    return fee


def settle_invoice(conn, invoice_id, amount=None, method="card", as_of=None):
    """Pay an invoice in full, including any late fee owed as of the payment date."""
    as_of = parse_date(as_of or dt.date.today())
    invoice = get_invoice(conn, invoice_id)
    if invoice["status"] != "open":
        raise InvalidInvoiceState(invoice["status"])
    accrue_late_fee(conn, invoice, as_of)
    invoice = get_invoice(conn, invoice_id)
    balance = invoice_balance(invoice)
    paid = balance if amount is None else to_money(amount)
    if paid < balance:
        raise PaymentTooSmall(f"{paid} is less than the balance {balance}")
    conn.execute("INSERT INTO payments(invoice_id, amount, method, received_on) VALUES (?,?,?,?)",
                 (invoice_id, str(paid), method, str(as_of)))
    conn.execute("UPDATE invoices SET paid = ?, status = 'paid' WHERE id = ?", (str(invoice["paid"] + paid), invoice_id))
    post_entry(conn, "cash", paid, f"payment {invoice['number']}", as_of, invoice["legacy_ref"])
    post_entry(conn, "receivables", -paid, f"payment {invoice['number']}", as_of, invoice["legacy_ref"])
    customer = customers.get_customer(conn, invoice["customer_id"])
    events.publish(conn, "invoice.settled", events.invoice_settled_payload(get_invoice(conn, invoice_id), customer, paid, as_of), as_of)
    conn.commit()
    return get_invoice(conn, invoice_id)


def void_invoice(conn, invoice_id, as_of=None):
    invoice = get_invoice(conn, invoice_id)
    if invoice["status"] != "open" or invoice["paid"] > ZERO:
        raise InvalidInvoiceState("only unpaid open invoices can be voided")
    as_of = parse_date(as_of or dt.date.today())
    post_entry(conn, "receivables", -invoice_total(invoice), f"void {invoice['number']}", as_of, invoice["legacy_ref"])
    post_entry(conn, "revenue", invoice["subtotal"] - invoice["discount"], f"void {invoice['number']}", as_of, invoice["legacy_ref"])
    conn.execute("UPDATE invoices SET status = 'void' WHERE id = ?", (invoice_id,))
    conn.commit()
    return get_invoice(conn, invoice_id)
