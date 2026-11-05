from pathlib import Path

import yaml

from billing.api.app import app


def new_customer(client, email="a@b.test", **kw):
    return client.post("/customers", json={"name": "A", "email": email, **kw}).json()


def new_invoice(client, customer_id, price="100.00", issue="2026-01-01"):
    r = client.post("/invoices", json={"customer_id": customer_id, "issue_date": issue, "lines": [{"description": "x", "quantity": 1, "unit_price": price}]})
    assert r.status_code == 201
    return r.json()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_customer_roundtrip(client):
    c = new_customer(client)
    assert client.get(f"/customers/{c['id']}").json()["email"] == "a@b.test"
    assert client.post("/customers", json={"name": "A", "email": "a@b.test"}).status_code == 409
    assert client.get("/customers/999").status_code == 404
    assert len(client.get("/customers").json()) == 1


def test_invoice_flow(client):
    c = new_customer(client)
    inv = new_invoice(client, c["id"], "40.20")
    assert inv["status"] == "open" and client.get(f"/invoices/{inv['id']}").status_code == 200
    r = client.post(f"/invoices/{inv['id']}/settle", json={"as_of": "2026-03-01"})
    assert r.status_code == 200 and r.json()["status"] == "paid"
    assert client.post(f"/invoices/{inv['id']}/settle", json={}).status_code == 409


def test_payment_and_credit_routes(client):
    c = new_customer(client)
    inv = new_invoice(client, c["id"])
    assert client.post(f"/invoices/{inv['id']}/payments", json={"amount": "10.00", "received_on": "2026-01-02"}).status_code == 201
    assert len(client.get(f"/invoices/{inv['id']}/payments").json()) == 1
    assert client.post(f"/invoices/{inv['id']}/credits", json={"amount": "5.00", "reason": "r"}).status_code == 201
    assert client.post(f"/invoices/{inv['id']}/payments", json={"amount": "999.00"}).status_code == 422


def test_void_route(client):
    c = new_customer(client)
    inv = new_invoice(client, c["id"])
    assert client.post(f"/invoices/{inv['id']}/void").json()["status"] == "void"
    assert client.post(f"/invoices/{inv['id']}/void").status_code == 409


def test_statement_and_revenue_routes(client):
    c = new_customer(client)
    new_invoice(client, c["id"])
    assert client.get(f"/customers/{c['id']}/statement", params={"as_of": "2026-03-01"}).json()["in_arrears"] is True
    assert client.get("/reports/revenue", params={"day": "2026-01-15"}).json()["net"] == "100.00"


def test_openapi_file_matches_routes():
    """Every route in the app appears in the published contract, and the reverse."""
    published = yaml.safe_load((Path(__file__).resolve().parent.parent / "openapi.yaml").read_text())
    live = app.openapi()
    assert {p: sorted(v) for p, v in published["paths"].items()} == {p: sorted(v) for p, v in live["paths"].items()}
