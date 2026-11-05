from pathlib import Path

import yaml

PUBLISHED = {"id", "number", "customer_id", "issue_date", "due_date", "subtotal", "discount", "tax", "late_fee", "total", "paid",
             "balance", "currency", "status"}


def test_published_fields_still_returned(client_factory):
    client = client_factory()
    c = client.post("/customers", json={"name": "A", "email": "a@b.test"}).json()
    inv = client.post("/invoices", json={"customer_id": c["id"], "issue_date": "2026-01-01",
                                         "lines": [{"description": "x", "quantity": 1, "unit_price": "1.00"}]}).json()
    assert PUBLISHED <= set(inv)


def test_contract_file_keeps_fields():
    spec = yaml.safe_load(Path("openapi.yaml").read_text())
    assert PUBLISHED <= set(spec["components"]["schemas"]["InvoiceOut"]["properties"])
