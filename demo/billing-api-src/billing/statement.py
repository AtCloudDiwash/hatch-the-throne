"""Customer account statements."""
from billing.customers import get_customer
from billing.dates import days_overdue
from billing.invoices import invoice_balance, invoice_total, list_invoices
from billing.money import ZERO, sum_money


def customer_statement(conn, customer_id, as_of):
    customer = get_customer(conn, customer_id)
    rows = []
    for invoice in list_invoices(conn, customer_id=customer_id):
        if invoice["status"] == "void":
            continue
        rows.append({
            "number": invoice["number"],
            "due_date": invoice["due_date"],
            "total": invoice_total(invoice),
            "balance": invoice_balance(invoice),
            "days_overdue": days_overdue(invoice["due_date"], as_of) if invoice["status"] == "open" else 0,
        })
    outstanding = sum_money(r["balance"] for r in rows)
    return {"customer": customer["name"], "as_of": str(as_of), "lines": rows, "outstanding": outstanding,
            "in_arrears": any(r["days_overdue"] > 0 and r["balance"] > ZERO for r in rows)}
