"""Dunning: escalating reminders for overdue invoices."""
from billing import customers, events, invoices
from billing.dates import days_overdue, parse_date

LEVELS = [(60, 3), (30, 2), (1, 1)]


def dunning_level(days):
    for floor, level in LEVELS:
        if days >= floor:
            return level
    return 0


def run_dunning(conn, as_of):
    as_of = parse_date(as_of)
    sent = []
    for invoice in invoices.list_invoices(conn, status="open"):
        days = days_overdue(invoice["due_date"], as_of)
        level = dunning_level(days)
        if level:
            customer = customers.get_customer(conn, invoice["customer_id"])
            events.publish(conn, "invoice.overdue", events.invoice_overdue_payload(invoice, customer, days, level), as_of)
            sent.append((invoice["number"], level))
    conn.commit()
    return sent
