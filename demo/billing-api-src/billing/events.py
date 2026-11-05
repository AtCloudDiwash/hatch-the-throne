"""Events written to the outbox for the notification service."""
import json

from billing.dates import parse_date


def invoice_settled_payload(invoice, customer, amount, settled_on):
    return {
        "invoice_number": invoice["number"],
        "customer_email": customer["email"],
        "amount": str(amount),
        "late_fee": str(invoice["late_fee"]),
        "currency": invoice["currency"],
        "settled_on": str(parse_date(settled_on)),
    }


def invoice_overdue_payload(invoice, customer, days, level):
    return {
        "invoice_number": invoice["number"],
        "customer_email": customer["email"],
        "days_overdue": days,
        "dunning_level": level,
    }


def publish(conn, event_type, payload, created_on):
    conn.execute("INSERT INTO outbox(event_type, payload, created_on) VALUES (?,?,?)",
                 (event_type, json.dumps(payload, sort_keys=True), str(created_on)))


def pending_events(conn, event_type=None):
    if event_type:
        rows = conn.execute("SELECT * FROM outbox WHERE event_type = ? ORDER BY id", (event_type,))
    else:
        rows = conn.execute("SELECT * FROM outbox ORDER BY id")
    return [{**dict(r), "payload": json.loads(r["payload"])} for r in rows]
