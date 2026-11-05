from decimal import Decimal as D

from jobs import dunning
from reports import revenue
from tests.conftest import make_invoice


def test_dunning_levels():
    assert [dunning.dunning_level(d) for d in (0, 1, 30, 60)] == [0, 1, 2, 3]


def test_run_dunning_publishes(conn, customer):
    inv = make_invoice(conn, customer, "100.00")
    assert dunning.run_dunning(conn, "2026-03-05") == [(inv["number"], 2)]


def test_monthly_revenue(conn, customer):
    make_invoice(conn, customer, "100.00", "2026-01-10")
    make_invoice(conn, customer, "50.00", "2026-02-10")
    assert revenue.monthly_revenue(conn, "2026-01-20")["net"] == D("100.00")
    assert revenue.quarterly_net(conn, 2026, 1) == D("150.00")
