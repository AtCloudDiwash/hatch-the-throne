"""T3.6: impact library."""
import sys

import pytest

from conftest import REPO, commit_all
from guardlib import config as cfgmod
from guardlib import impact
from indexer import db

sys.path.insert(0, str(REPO / "demo"))
import build_billing_repo as builder  # noqa: E402


@pytest.fixture(scope="module")
def billing(tmp_path_factory):
    dest = tmp_path_factory.mktemp("bill") / "billing-api"
    builder.build(dest)
    from indexer.__main__ import refresh
    cfg = cfgmod.load_config(str(dest))
    refresh(cfg, with_tests=True)
    return cfg, db.connect(str(dest))


def test_fr09_output_for_compute_late_fee(billing):
    cfg, conn = billing
    text = impact.impact_text(conn, cfg, "compute_late_fee")
    print(text)
    assert "accrue_late_fee() [names,tests]" in text
    assert "projected_fee() [names, history 71%]" not in text  # sources are comma-joined
    assert "projected_fee() [names,history 71%] no test reaches it" in text
    assert "aging_bucket() [names] no test reaches it" in text
    assert "POST /invoices/{invoice_id}/settle [routes]" in text
    assert "db/rates.sql [history 82%]" in text
    assert len(text) <= 1500


def test_every_item_carries_sources(billing):
    cfg, conn = billing
    imp = impact.compute(conn, cfg, "compute_late_fee")
    assert imp.callers and all(c["sources"] for c in imp.callers)
    assert imp.routes and all(r["sources"] == ["routes"] for r in imp.routes)
    assert imp.cochange and all(c["sources"] for c in imp.cochange)
    assert len(imp.tests) >= 6


def test_callers_reach_three_hops(billing):
    cfg, conn = billing
    imp = impact.compute(conn, cfg, "compute_late_fee")
    hops = {(c["file"], c["qualname"]): c["hop"] for c in imp.callers}
    assert hops[("billing/invoices.py", "accrue_late_fee")] == 1
    assert hops[("billing/invoices.py", "settle_invoice")] == 2
    assert hops[("billing/api/invoices.py", "settle_invoice")] == 3
    assert hops[("jobs/close_month.py", "close_month")] == 2
    assert max(hops.values()) <= 3
    shallow = impact.compute(conn, cfg, "compute_late_fee", depth=1)
    assert {c["hop"] for c in shallow.callers} == {1}


def test_frozen_flag(billing):
    cfg, conn = billing
    assert impact.compute(conn, cfg, "post_entry").frozen is True
    assert "frozen   yes [rule]" in impact.impact_text(conn, cfg, "post_entry")


def test_output_size_bound_with_truncation_count(billing):
    cfg, conn = billing
    imp = impact.compute(conn, cfg, "compute_late_fee")
    imp.callers = [{"qualname": f"caller_with_a_very_long_name_{i}", "file": "x.py", "sources": ["names"], "hop": 1} for i in range(500)]
    imp.routes = [{"route": f"GET /a/very/long/route/{'x' * 300}/{i}", "sources": ["routes"]} for i in range(6)]
    text = impact.render(imp)
    assert len(text) <= 1500 and "500 callers in total" in text


def test_unknown_symbol(billing):
    cfg, conn = billing
    assert "not found" in impact.impact_text(conn, cfg, "no_such_function_anywhere")


def test_same_named_functions_all_counted(repo):
    (repo / "a.py").write_text("def run():\n    pass\n\ndef use_a():\n    run()\n")
    (repo / "b.py").write_text("def run():\n    pass\n\ndef use_b():\n    run()\n")
    commit_all(repo)
    from indexer.__main__ import refresh
    cfg = cfgmod.load_config(str(repo))
    refresh(cfg)
    conn = db.connect(str(repo))
    assert {c["qualname"] for c in impact.compute(conn, cfg, "run").callers} == {"use_a", "use_b"}


def test_missing_coverage_says_so(repo):
    from indexer.__main__ import refresh
    cfg = cfgmod.load_config(str(repo))
    refresh(cfg)
    conn = db.connect(str(repo))
    assert "unknown: no coverage map" in impact.impact_text(conn, cfg, "add")
