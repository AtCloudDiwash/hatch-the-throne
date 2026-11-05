"""FastAPI application."""
from fastapi import FastAPI

from billing.api import customers, invoices, reports

app = FastAPI(title="billing-api", version="1.4.0")
app.include_router(customers.router)
app.include_router(invoices.router)
app.include_router(reports.router)


@app.get("/health")
def health():
    return {"status": "ok"}
