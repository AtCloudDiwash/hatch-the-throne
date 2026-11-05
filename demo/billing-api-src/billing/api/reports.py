"""Reporting routes."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from billing import db, invoices
from billing.api import schemas
from billing.api.deps import get_conn
from reports import aging, revenue

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/aging/{invoice_id}", response_model=schemas.AgingOut)
def invoice_aging(invoice_id: int, as_of: str):
    try:
        row = aging.aging_bucket(invoice_id, as_of, db.db_path())
    except invoices.InvoiceNotFound as exc:
        raise HTTPException(404, "invoice not found") from exc
    return {"bucket": row["bucket"], "balance": str(row["balance"]), "projected_fee": str(row["projected_fee"])}


@router.get("/revenue", response_model=schemas.RevenueOut)
def month_revenue(day: str, conn: sqlite3.Connection = Depends(get_conn)):
    row = revenue.monthly_revenue(conn, day)
    return {**row, "net": str(row["net"]), "tax": str(row["tax"]), "late_fees": str(row["late_fees"])}
