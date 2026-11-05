"""Held-out fixtures. The harness runs these with the clone as the working directory."""
import pytest

from billing import customers, db


@pytest.fixture
def db_file(tmp_path, monkeypatch):
    path = tmp_path / "check.db"
    monkeypatch.setenv("BILLING_DB", str(path))
    return str(path)


@pytest.fixture
def conn(db_file):
    connection = db.connect(db_file)
    db.init_db(connection)
    yield connection
    connection.close()


@pytest.fixture
def customer(conn):
    return customers.create_customer(conn, "Check Co", "check@example.test", created_on="2026-01-01")


def line(amount):
    return [{"description": "x", "quantity": 1, "unit_price": amount}]


@pytest.fixture
def client_factory(conn):
    from fastapi.testclient import TestClient

    from billing.api.app import app
    return lambda: TestClient(app)
