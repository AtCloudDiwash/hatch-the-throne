"""Customer routes."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from billing import customers, statement
from billing.api import schemas
from billing.api.deps import get_conn

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("", response_model=schemas.CustomerOut, status_code=201)
def create_customer(body: schemas.CustomerIn, conn: sqlite3.Connection = Depends(get_conn)):
    try:
        return customers.create_customer(conn, **body.model_dump())
    except customers.DuplicateEmail as exc:
        raise HTTPException(409, "email already registered") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("", response_model=list[schemas.CustomerOut])
def list_customers(tier: str | None = None, conn: sqlite3.Connection = Depends(get_conn)):
    return customers.list_customers(conn, tier)


@router.get("/{customer_id}", response_model=schemas.CustomerOut)
def get_customer(customer_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    try:
        return customers.get_customer(conn, customer_id)
    except customers.CustomerNotFound as exc:
        raise HTTPException(404, "customer not found") from exc


@router.get("/{customer_id}/statement", response_model=schemas.StatementOut)
def get_statement(customer_id: int, as_of: str, conn: sqlite3.Connection = Depends(get_conn)):
    try:
        data = statement.customer_statement(conn, customer_id, as_of)
    except customers.CustomerNotFound as exc:
        raise HTTPException(404, "customer not found") from exc
    data["outstanding"] = str(data["outstanding"])
    data["lines"] = [{**line, "total": str(line["total"]), "balance": str(line["balance"])} for line in data["lines"]]
    return data
