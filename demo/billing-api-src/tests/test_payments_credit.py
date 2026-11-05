from decimal import Decimal as D

import pytest

from billing import credit, invoices, payments, statement
from tests.conftest import make_invoice


def test_partial_then_final_payment(conn, customer):
    inv = make_invoice(conn, customer, "100.00")
    assert payments.record_payment(conn, inv["id"], "40.00", received_on="2026-01-05")["status"] == "open"
    assert payments.record_payment(conn, inv["id"], "60.00", received_on="2026-01-06")["status"] == "paid"
    assert payments.total_received(conn, inv["id"]) == D("100.00")


def test_overpayment_rejected(conn, customer):
    inv = make_invoice(conn, customer, "100.00")
    with pytest.raises(payments.Overpayment):
        payments.record_payment(conn, inv["id"], "100.01")


def test_refund_reopens(conn, customer):
    inv = make_invoice(conn, customer, "100.00")
    payments.record_payment(conn, inv["id"], "100.00", received_on="2026-01-05")
    pid = payments.payments_for_invoice(conn, inv["id"])[0]["id"]
    refunded = payments.refund_payment(conn, pid, "2026-01-06")
    assert refunded["status"] == "open" and invoices.invoice_balance(refunded) == D("100.00")


def test_credit_note_reduces_balance(conn, customer):
    inv = make_invoice(conn, customer, "100.00")
    credit.issue_credit_note(conn, inv["id"], "25.00", "goodwill", "2026-01-05")
    assert invoices.invoice_balance(invoices.get_invoice(conn, inv["id"])) == D("75.00")
    assert credit.credit_total(conn, inv["id"]) == D("25.00")
    with pytest.raises(ValueError):
        credit.issue_credit_note(conn, inv["id"], "500.00", "too much", "2026-01-05")


def test_statement(conn, customer):
    make_invoice(conn, customer, "100.00")
    s = statement.customer_statement(conn, customer["id"], "2026-03-01")
    assert s["outstanding"] == D("100.00") and s["in_arrears"] and s["lines"][0]["days_overdue"] == 29
