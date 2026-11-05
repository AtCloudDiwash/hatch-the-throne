"""Request and response bodies published in openapi.yaml."""
from pydantic import BaseModel, Field


class CustomerIn(BaseModel):
    name: str
    email: str
    tier: str = "standard"
    region: str = "NONE"
    payment_terms_days: int = Field(default=30, ge=0, le=120)


class CustomerOut(BaseModel):
    id: int
    name: str
    email: str
    tier: str
    region: str
    payment_terms_days: int


class LineIn(BaseModel):
    description: str
    quantity: int = Field(gt=0)
    unit_price: str


class InvoiceIn(BaseModel):
    customer_id: int
    lines: list[LineIn]
    issue_date: str | None = None
    currency: str = "USD"


class InvoiceOut(BaseModel):
    id: int
    number: str
    customer_id: int
    issue_date: str
    due_date: str
    subtotal: str
    discount: str
    tax: str
    late_fee: str
    total: str
    paid: str
    balance: str
    currency: str
    status: str


class SettleIn(BaseModel):
    amount: str | None = None
    method: str = "card"
    as_of: str | None = None


class PaymentIn(BaseModel):
    amount: str
    method: str = "card"
    received_on: str | None = None


class PaymentOut(BaseModel):
    id: int
    invoice_id: int
    amount: str
    method: str
    received_on: str


class CreditIn(BaseModel):
    amount: str
    reason: str
    issued_on: str | None = None


class CreditOut(BaseModel):
    id: int
    invoice_id: int
    amount: str
    reason: str
    issued_on: str


class AgingOut(BaseModel):
    bucket: str
    balance: str
    projected_fee: str


class RevenueOut(BaseModel):
    month: str
    invoices: int
    net: str
    tax: str
    late_fees: str


class StatementLine(BaseModel):
    number: str
    due_date: str
    total: str
    balance: str
    days_overdue: int


class StatementOut(BaseModel):
    customer: str
    as_of: str
    lines: list[StatementLine]
    outstanding: str
    in_arrears: bool
