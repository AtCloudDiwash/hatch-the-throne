"""T3.2, T3.3, T3.4: coverage map, routes and contracts, co-change, on fixtures and billing-api."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO, commit_all
from guardlib import config as cfgmod
from guardlib import contracts_parse as cp
from indexer import coverage_map, db, history, names, routes

sys.path.insert(0, str(REPO / "demo"))
import build_billing_repo as builder  # noqa: E402

PY = sys.executable


@pytest.fixture
def tiny(repo):
    """Known tests on known functions."""
    (repo / ".legacyguard" / "config.yaml").write_text(f"scope: .\nmode: guarded\npython: {PY}\n")
    (repo / "calc.py").write_text("from decimal import Decimal\n\ndef double(x):\n    return x * 2\n\ndef triple(x):\n    return x * 3\n\ndef unused(x):\n    return x\n\ndef via(x):\n    return double(x)\n\nclass Box:\n    def __init__(self, v):\n        self.v = v\n    def size(self):\n        return self.v\n")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_calc.py").write_text("from decimal import Decimal\nimport calc\n\ndef test_a():\n    assert calc.double(2) == 4\n\ndef test_b():\n    assert calc.double(Decimal('1.5')) == 3\n\ndef test_c():\n    assert calc.via(1) == 2\n\ndef test_d():\n    assert calc.triple(1) == 3\n\ndef test_e():\n    assert calc.Box(4).size() == 4\n")
    (repo / "pytest.ini").write_text("[pytest]\npythonpath = .\n")
    commit_all(repo, "tiny")
    return repo


def test_map_from_tiny_fixture(tiny):
    cfg = cfgmod.load_config(str(tiny))
    conn = db.connect(str(tiny))
    r = coverage_map.build(conn, cfg)
    assert r["status"] == "ok", r
    got = {}
    for row in conn.execute("SELECT test_id, qualname FROM test_cover WHERE file='calc.py'"):
        got.setdefault(row["qualname"], set()).add(row["test_id"].rsplit(".", 1)[-1])
    assert got["double"] == {"test_a", "test_b", "test_c"}
    assert got["triple"] == {"test_d"} and got["via"] == {"test_c"} and got["Box.size"] == {"test_e"}
    assert "unused" not in got


def test_harvest_records_arguments(tiny):
    cfg = cfgmod.load_config(str(tiny))
    coverage_map.build(db.connect(str(tiny)), cfg)
    harvest = coverage_map.load_harvest(cfg)
    values = [i[0]["value"] for i in harvest["calc.py::double"]["inputs"]]
    assert {"t": "Decimal", "v": "1.5"} in values and {"t": "v", "v": 2} in values
    assert harvest["calc.py::Box.size"]["inputs"][0][0]["name"] == "self"


def test_failing_suite_records_status(tiny):
    (tiny / "tests" / "test_bad.py").write_text("def test_no():\n    assert False\n")
    r = coverage_map.build(db.connect(str(tiny)), cfgmod.load_config(str(tiny)))
    assert r["status"] == "tests exited 1" and r["rows"] > 0


def test_guard_leaves_no_files_outside_state_dir(tiny):
    coverage_map.build(db.connect(str(tiny)), cfgmod.load_config(str(tiny)))
    status = subprocess.run(["git", "-C", str(tiny), "status", "--short"], capture_output=True, text=True).stdout
    assert all(".legacyguard" in line for line in status.splitlines()), status


SPEC = """
openapi: 3.1.0
paths:
  /things/{id}:
    get:
      parameters:
        - {name: id, in: path, schema: {type: integer}}
components:
  schemas:
    Thing:
      properties:
        id: {type: integer}
        price: {type: string}
"""


def test_http_items_and_drop():
    before = cp.http_items(SPEC)
    assert before["route:GET /things/{id}"] == "route" and before["field:Thing.price"] == "string"
    assert before["param:GET /things/{id}:id"] == "integer"
    assert cp.response_field_names(before) == {"id", "price"} and cp.schema_names(before) == {"Thing"}
    after = cp.http_items(SPEC.replace("        price: {type: string}\n", ""))
    assert set(before) - set(after) == {"field:Thing.price"}


def test_db_schema_from_real_sql():
    s = cp.sql_schema(["CREATE TABLE t (a INTEGER, b TEXT);", "ALTER TABLE t DROP COLUMN b;"])
    assert s == {"column:t.a": "INTEGER"}
    assert cp.sql_schema(["NOT SQL AT ALL"]) is None


@pytest.mark.parametrize("text,item", [
    ("ALTER TABLE t DROP COLUMN legacy_ref;", "column dropped:legacy_ref"),
    ("ALTER TABLE t RENAME COLUMN a TO b;", "column renamed:a"),
    ("DROP TABLE IF EXISTS old;", "table dropped:old"),
    ("ALTER TABLE t ALTER COLUMN a TYPE text;", "column retyped:a"),
    ("migrations.RemoveField(model_name='x', name='price')", "column dropped:price"),
    ("migrations.RenameField(model_name='x', old_name='a', new_name='b')", "column renamed:a"),
])
def test_dangerous_statements(text, item):
    assert item in cp.dangerous_statements(text)


def test_comment_is_not_a_statement():
    assert cp.dangerous_statements("-- DROP TABLE x\nSELECT 1;") == {}


def test_event_items_retype():
    doc = '{"title": "e", "properties": {"a": {"type": "string"}, "b": {"type": "integer"}}}'
    assert cp.event_items("f", doc) == {"field:e.a": "string", "field:e.b": "integer"}
    assert cp.event_items("f", "not json") == {}


def test_cochange_support_and_confidence():
    groups = [["a", "b"]] * 3 + [["a", "c"]] + [["x"] * 1 + [f"f{i}" for i in range(40)]]
    rows = {(a, b): (s, c) for a, b, s, c in history.compute(groups)}
    assert rows[("a", "b")] == (3, 0.75) and rows[("b", "a")] == (3, 1.0)
    assert ("a", "c") not in rows, "below minimum support"
    assert not any(k[0].startswith("f") for k in rows), "bulk commits ignored"


@pytest.fixture(scope="module")
def billing(tmp_path_factory):
    dest = tmp_path_factory.mktemp("bill") / "billing-api"
    builder.build(dest)
    from indexer.__main__ import refresh
    refresh(cfgmod.load_config(str(dest)), with_tests=True)
    return dest


def test_every_openapi_route_maps_to_a_handler(billing):
    conn = db.connect(str(billing))
    cfg = cfgmod.load_config(str(billing))
    assert conn.execute("SELECT DISTINCT source FROM routes").fetchone()["source"] == "framework"
    live = {(r["method"], r["path"]): (r["handler_qualname"], r["handler_file"]) for r in conn.execute("SELECT * FROM routes")}
    spec = cp.http_items((billing / "openapi.yaml").read_text())
    published = {tuple(k[len("route:"):].split(" ")) for k in spec if k.startswith("route:")}
    assert published == set(live)
    assert live[("POST", "/invoices/{invoice_id}/settle")] == ("settle_invoice", "billing/api/invoices.py")
    assert conn.execute("SELECT COUNT(*) FROM contracts WHERE kind='db' AND item='column:invoices.currency'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM contracts WHERE kind='messages' AND item='field:invoice.settled.customer_email'").fetchone()[0] == 1


def test_billing_coverage_matches_manual_check_on_three_functions(billing):
    conn = db.connect(str(billing))
    def tests_of(file, qual):
        return {r["test_id"].rsplit(".", 1)[-1] for r in conn.execute("SELECT test_id FROM test_cover WHERE file=? AND qualname=?", (file, qual))}
    assert tests_of("billing/dates.py", "quarter_of") >= {"test_quarter"}
    assert tests_of("billing/tax.py", "tax_rate") >= {"test_compute_tax"}
    assert "test_late_fee_simple_percentage" in tests_of("billing/fees.py", "compute_late_fee")
    assert tests_of("reports/aging.py", "aging_bucket") == set()
    assert tests_of("jobs/close_month.py", "close_month") == set()


def test_billing_harvest_has_the_counterexample_input(billing):
    harvest = coverage_map.load_harvest(cfgmod.load_config(str(billing)))
    inputs = harvest["billing/fees.py::compute_late_fee"]["inputs"]
    pairs = [(i[0]["value"], i[1]["value"]) for i in inputs]
    assert ({"t": "Decimal", "v": "40.20"}, {"t": "Decimal", "v": "0.025"}) in pairs
    assert "conn" in harvest["billing/invoices.py::settle_invoice"]["blocked"]


def test_billing_planted_pair_reported(billing):
    conn = db.connect(str(billing))
    row = conn.execute("SELECT * FROM cochange WHERE file_a='billing/fees.py' AND file_b='db/rates.sql'").fetchone()
    assert row["support"] == 14 and round(row["confidence"], 2) == 0.82
    row = conn.execute("SELECT * FROM cochange WHERE file_a='billing/fees.py' AND file_b='jobs/close_month.py'").fetchone()
    assert round(row["confidence"], 2) == 0.71


def test_billing_status_stays_clean(billing):
    out = subprocess.run(["git", "-C", str(billing), "status", "--short"], capture_output=True, text=True).stdout
    assert all(".legacyguard" in l for l in out.splitlines()), out
