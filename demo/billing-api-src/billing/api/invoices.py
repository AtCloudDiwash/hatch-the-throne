"""Invoice, payment and credit routes."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from billing import credit, invoices, payments
from billing.api import schemas
from billing.api.deps import get_conn
from billing.customers import CustomerNotFound

router = APIRouter(prefix="/invoices", tags=["invoices"])


def serialize(invoice):
    return {
        "id": invoice["id"],
        "number": invoice["number"],
        "customer_id": invoice["customer_id"],
        "issue_date": invoice["issue_date"],
        "due_date": invoice["due_date"],
        "subtotal": str(invoice["subtotal"]),
        "discount": str(invoice["discount"]),
        "tax": str(invoice["tax"]),
        "late_fee": str(invoice["late_fee"]),
        "total": str(invoices.invoice_total(invoice)),
        "paid": str(invoice["paid"]),
        "balance": str(invoices.invoice_balance(invoice)),
        "currency": invoice["currency"],
        "status": invoice["status"],
    }


def load(conn, invoice_id):
    try:
        return invoices.get_invoice(conn, invoice_id)
    except invoices.InvoiceNotFound as exc:
        raise HTTPException(404, "invoice not found") from exc


@router.post("", response_model=schemas.InvoiceOut, status_code=201)
def create_invoice(body: schemas.InvoiceIn, conn: sqlite3.Connection = Depends(get_conn)):
    try:
        lines = [line.model_dump() for line in body.lines]
        return serialize(invoices.create_invoice(conn, body.customer_id, lines, body.issue_date, body.currency))
    except CustomerNotFound as exc:
        raise HTTPException(404, "customer not found") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("", response_model=list[schemas.InvoiceOut])
def list_invoices(customer_id: int | None = None, status: str | None = None, conn: sqlite3.Connection = Depends(get_conn)):
    return [serialize(i) for i in invoices.list_invoices(conn, customer_id, status)]


@router.get("/{invoice_id}", response_model=schemas.InvoiceOut)
def get_invoice(invoice_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    return serialize(load(conn, invoice_id))


@router.post("/{invoice_id}/settle", response_model=schemas.InvoiceOut)
def settle_invoice(invoice_id: int, body: schemas.SettleIn, conn: sqlite3.Connection = Depends(get_conn)):
    load(conn, invoice_id)
    try:
        return serialize(invoices.settle_invoice(conn, invoice_id, body.amount, body.method, body.as_of))
    except invoices.InvalidInvoiceState as exc:
        raise HTTPException(409, f"invoice is {exc}") from exc
    except invoices.PaymentTooSmall as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/{invoice_id}/void", response_model=schemas.InvoiceOut)
def void_invoice(invoice_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    load(conn, invoice_id)
    try:
        return serialize(invoices.void_invoice(conn, invoice_id))
    except invoices.InvalidInvoiceState as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/{invoice_id}/payments", response_model=schemas.InvoiceOut, status_code=201)
def add_payment(invoice_id: int, body: schemas.PaymentIn, conn: sqlite3.Connection = Depends(get_conn)):
    load(conn, invoice_id)
    try:
        return serialize(payments.record_payment(conn, invoice_id, body.amount, body.method, body.received_on))
    except (payments.Overpayment, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except invoices.InvalidInvoiceState as exc:
        raise HTTPException(409, f"invoice is {exc}") from exc


@router.get("/{invoice_id}/payments", response_model=list[schemas.PaymentOut])
def list_payments(invoice_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    load(conn, invoice_id)
    return payments.payments_for_invoice(conn, invoice_id)


@router.post("/{invoice_id}/credits", response_model=schemas.CreditOut, status_code=201)
def add_credit(invoice_id: int, body: schemas.CreditIn, conn: sqlite3.Connection = Depends(get_conn)):
    load(conn, invoice_id)
    try:
        note = credit.issue_credit_note(conn, invoice_id, body.amount, body.reason, body.issued_on)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**note, "amount": str(note["amount"])}
