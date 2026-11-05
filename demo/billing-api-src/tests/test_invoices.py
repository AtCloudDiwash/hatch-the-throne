from decimal import Decimal as D

import pytest

from billing import customers, events, invoices
from legacy import ledger_v1
from tests.conftest import make_invoice


def test_create_invoice_totals(conn):
    c = customers.create_customer(conn, "Taxed", "t@x.test", region="MS", created_on="2026-01-01")
    inv = invoices.create_invoice(conn, c["id"], [{"description": "A", "quantity": 2, "unit_price": "50.00"}], "2026-01-01")
    assert inv["subtotal"] == D("100.00") and inv["tax"] == D("7.00")
    assert invoices.invoice_total(inv) == D("107.00") and inv["number"] == "INV-2026-00001"
    assert inv["due_date"] == "2026-01-31"


def test_invoice_requires_lines(conn, customer):
    with pytest.raises(ValueError):
        invoices.create_invoice(conn, customer["id"], [], "2026-01-01")


def test_settle_on_time_has_no_fee(conn, customer):
    inv = make_invoice(conn, customer, "100.00")
    paid = invoices.settle_invoice(conn, inv["id"], as_of="2026-01-20")
    assert paid["status"] == "paid" and paid["late_fee"] == D("0.00")


def test_settle_overdue_invoice_is_paid_in_full(conn, customer):
    inv = make_invoice(conn, customer, "40.20")
    paid = invoices.settle_invoice(conn, inv["id"], as_of="2026-03-01")
    assert paid["status"] == "paid"
    assert invoices.invoice_balance(paid) == D("0.00")


def test_settle_overdue_adds_some_fee(conn, customer):
    inv = make_invoice(conn, customer, "200.00")
    paid = invoices.settle_invoice(conn, inv["id"], as_of="2026-03-01")
    assert paid["late_fee"] > D("0")


def test_settle_rejects_small_payment(conn, customer):
    inv = make_invoice(conn, customer, "100.00")
    with pytest.raises(invoices.PaymentTooSmall):
        invoices.settle_invoice(conn, inv["id"], amount="1.00", as_of="2026-01-10")


def test_settle_twice_is_invalid(conn, customer):
    inv = make_invoice(conn, customer, "100.00")
    invoices.settle_invoice(conn, inv["id"], as_of="2026-01-10")
    with pytest.raises(invoices.InvalidInvoiceState):
        invoices.settle_invoice(conn, inv["id"], as_of="2026-01-11")


def test_settle_publishes_event(conn, customer):
    inv = make_invoice(conn, customer, "100.00")
    invoices.settle_invoice(conn, inv["id"], as_of="2026-01-10")
    event = events.pending_events(conn, "invoice.settled")[0]["payload"]
    assert event["invoice_number"] == inv["number"] and event["customer_email"] == "ap@acme.test"


def test_void_invoice(conn, customer):
    inv = make_invoice(conn, customer, "100.00")
    assert invoices.void_invoice(conn, inv["id"], "2026-01-02")["status"] == "void"
    with pytest.raises(invoices.InvalidInvoiceState):
        invoices.void_invoice(conn, inv["id"], "2026-01-03")


def test_ledger_balances_after_settlement(conn, customer):
    inv = make_invoice(conn, customer, "100.00")
    invoices.settle_invoice(conn, inv["id"], as_of="2026-03-01")
    balances = ledger_v1.trial_balance(conn)
    assert balances["receivables"] == D("0.00") and sum(balances.values()) == D("0.00")
    assert balances["cash"] > D("100")
