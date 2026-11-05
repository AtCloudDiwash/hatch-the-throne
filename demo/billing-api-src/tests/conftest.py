import pytest
from fastapi.testclient import TestClient

from billing import customers, db, invoices


@pytest.fixture
def db_file(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setenv("BILLING_DB", str(path))
    return str(path)


@pytest.fixture
def conn(db_file):
    connection = db.connect(db_file)
    db.init_db(connection)
    yield connection
    connection.close()


@pytest.fixture
def client(conn):
    from billing.api.app import app
    return TestClient(app)


@pytest.fixture
def customer(conn):
    return customers.create_customer(conn, "Acme", "ap@acme.test", created_on="2026-01-01")


def make_invoice(conn, customer, amount, issue_date="2026-01-01", qty=1):
    return invoices.create_invoice(conn, customer["id"], [{"description": "Service", "quantity": qty, "unit_price": amount}], issue_date)
