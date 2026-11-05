"""Monthly revenue report."""
from billing.dates import month_end, month_start, parse_date, quarter_of
from billing.invoices import list_invoices
from billing.money import ZERO, sum_money


def monthly_revenue(conn, day):
    start, end = month_start(day), month_end(day)
    rows = [i for i in list_invoices(conn) if i["status"] != "void" and start <= parse_date(i["issue_date"]) <= end]
    net = sum_money(i["subtotal"] - i["discount"] for i in rows)
    return {"month": str(start)[:7], "invoices": len(rows), "net": net, "tax": sum_money(i["tax"] for i in rows),
            "late_fees": sum_money(i["late_fee"] for i in rows)}


def quarterly_net(conn, year, quarter):
    total = ZERO
    for invoice in list_invoices(conn):
        issued = parse_date(invoice["issue_date"])
        if invoice["status"] != "void" and issued.year == year and quarter_of(issued) == quarter:
            total += invoice["subtotal"] - invoice["discount"]
    return total
