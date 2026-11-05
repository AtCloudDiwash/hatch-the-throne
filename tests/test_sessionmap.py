"""M9 (FR-30): session map model, text tree, HTML, Stop integration, map command."""
import json
import os
import shutil
import subprocess
import sys
import time

import pytest

from conftest import PLUGIN, REPO, git, run_script
from guardlib import config as cfgmod, impact, ledger, sessionmap
from indexer import db

sys.path.insert(0, str(REPO / "demo"))
import build_billing_repo as builder  # noqa: E402

GOOD = "fee = fee.quantize(CENT, ROUND_HALF_UP)"
BAD = "fee = round(fee, 2)"
FEE = "billing/fees.py::compute_late_fee"


@pytest.fixture(scope="module")
def pristine(tmp_path_factory):
    dest = tmp_path_factory.mktemp("b") / "billing-api"
    builder.build(dest)
    from indexer.__main__ import refresh
    refresh(cfgmod.load_config(str(dest)), with_tests=True)
    return dest


@pytest.fixture
def bill(pristine, tmp_path):
    work = tmp_path / "billing-api"
    shutil.copytree(pristine, work, symlinks=True)
    assert run_script("session_start", {"cwd": str(work), "session_id": "sess1", "source": "startup"}).returncode == 0
    return work


def change(repo, rel, old, new):
    p = repo / rel
    text = p.read_text()
    assert old in text
    p.write_text(text.replace(old, new))
    return run_script("post_edit", {"cwd": str(repo), "session_id": "sess1", "tool_name": "Edit", "tool_input": {"file_path": str(p)}})


def model(repo):
    cfg = cfgmod.load_config(str(repo))
    return sessionmap.build(cfg, ledger.load(cfg.state_dir))


def node(m, node_id):
    return next(n for n in m["nodes"] if n["id"] == node_id)


def edge(m, caller, callee):
    return next(e for e in m["edges"] if e["from"] == caller and e["to"] == callee)


# ---- T9.1 model and tree ----

def test_callers_record_which_function_they_call(bill):
    cfg = cfgmod.load_config(str(bill))
    imp = impact.compute(db.connect(str(bill)), cfg, "compute_late_fee")
    via = {(c["file"], c["qualname"]): c["via"] for c in imp.callers}
    assert via[("billing/invoices.py", "accrue_late_fee")] == "compute_late_fee"
    assert via[("billing/invoices.py", "settle_invoice")] == "accrue_late_fee"
    assert via[("billing/api/reports.py", "invoice_aging")] == "aging_bucket"
    assert {r["route"]: r["handler_qualname"] for r in imp.routes}["POST /invoices/{invoice_id}/settle"] == "settle_invoice"


def test_text_tree(bill):
    cfg = cfgmod.load_config(str(bill))
    tree = impact.render_tree(impact.compute(db.connect(str(bill)), cfg, "compute_late_fee"))
    print(tree)
    lines = tree.splitlines()
    assert lines[0] == "compute_late_fee  billing/fees.py"
    assert any(l.startswith("|- accrue_late_fee  billing/invoices.py  [names,tests]") for l in lines)
    assert any(l.startswith("|  |- settle_invoice  billing/invoices.py") for l in lines)
    assert any("aging_bucket  reports/aging.py  [names]  no test reaches it" in l for l in lines)
    assert any("settle_invoice  billing/api/invoices.py" in l and "<- POST /invoices/{invoice_id}/settle" in l for l in lines)
    assert len(lines) == 10, "the target and its 9 callers, each listed once"


def test_tree_is_capped():
    imp = impact.Impact("f", "a.py", callers=[{"qualname": f"c{i}", "file": "a.py", "hop": 1, "sources": ["names"], "via": "f"} for i in range(100)])
    lines = impact.render_tree(imp).splitlines()
    assert len(lines) == 41 and "more" in lines[-1]


def test_impact_command_prints_tree(bill):
    r = subprocess.run([sys.executable, str(PLUGIN / "scripts/lg.py"), "impact", "compute_late_fee", "--tree"], cwd=bill, capture_output=True, text=True,
                       env={**os.environ, "CLAUDE_PROJECT_DIR": str(bill)})
    assert "callers  " in r.stdout and "|- accrue_late_fee" in r.stdout


def test_model_for_the_rounding_edit(bill):
    assert change(bill, "billing/fees.py", GOOD, BAD).returncode == 2
    m = model(bill)
    fee = node(m, FEE)
    assert fee["kind"] == "changed" and fee["layer"] == 0 and fee["status"] == ledger.DIFFERENCE and fee["state"] == "open"
    assert "before 1.01 after 1.00" in fee["findings"][0]["evidence"] and fee["tests"] is True and fee["test_count"] >= 6
    assert any(c.startswith("db/rates.sql (82%)") for c in fee["cochange"])
    assert node(m, "billing/invoices.py::accrue_late_fee")["tests"] is True
    assert node(m, "jobs/close_month.py::projected_fee")["tests"] is False
    aging = node(m, "reports/aging.py::aging_bucket")
    assert aging["tests"] is False and aging["layer"] == 1 and aging["kind"] == "caller" and aging["status"] is None
    assert node(m, "billing/api/invoices.py::settle_invoice")["routes"] == ["POST /invoices/{invoice_id}/settle"]
    assert node(m, "billing/api/invoices.py::settle_invoice")["layer"] == 3
    assert m["counts"][ledger.DIFFERENCE] == 1 and m["prompts"] == 0 and m["wakeups"] == 1 and m["truncated"] == 0


def test_edges_are_solid_only_when_a_test_runs_both_ends(bill):
    change(bill, "billing/fees.py", GOOD, BAD)
    m = model(bill)
    assert edge(m, "billing/invoices.py::accrue_late_fee", FEE)["observed"] is True
    assert edge(m, "jobs/close_month.py::projected_fee", FEE)["observed"] is False
    assert edge(m, "reports/aging.py::aging_bucket", FEE)["observed"] is False
    assert edge(m, "billing/invoices.py::settle_invoice", "billing/invoices.py::accrue_late_fee")["observed"] is True
    assert edge(m, "billing/api/reports.py::invoice_aging", "reports/aging.py::aging_bucket")["observed"] is False
    ids = {n["id"] for n in m["nodes"]}
    assert all(e["from"] in ids and e["to"] in ids for e in m["edges"])


def test_revert_shows_verified_and_turned_back(bill):
    change(bill, "billing/fees.py", GOOD, BAD)
    assert change(bill, "billing/fees.py", BAD, GOOD).returncode == 0
    m = model(bill)
    fee = node(m, FEE)
    assert fee["status"] == ledger.VERIFIED and fee["turned_back"] is True and m["turned_back"] == 1
    assert [f["status"] for f in fee["findings"]] == [ledger.VERIFIED, ledger.DIFFERENCE]


def test_untested_changed_function_and_shared_callers(bill):
    change(bill, "billing/fees.py", GOOD, BAD)
    change(bill, "reports/aging.py", '"""Bucket and projected late fee for one invoice, read from the live database."""', '"""Bucket."""')
    m = model(bill)
    aging = node(m, "reports/aging.py::aging_bucket")
    assert aging["kind"] == "changed" and aging["layer"] == 0 and aging["status"] == ledger.UNTESTED
    assert edge(m, "reports/aging.py::aging_bucket", FEE), "a changed function that calls another changed one keeps its edge"
    assert len([n for n in m["nodes"] if n["id"] == "billing/api/reports.py::invoice_aging"]) == 1


def test_no_changes_and_no_index(bill, repo):
    m = model(bill)
    assert m["nodes"] == [] and m["edges"] == [] and m["findings"] == []
    assert run_script("session_start", {"cwd": str(repo), "session_id": "s", "source": "startup"}).returncode == 0
    (repo / ".legacyguard/index.db").unlink()
    assert model(repo)["index"] is False


def test_caller_cap(bill, monkeypatch):
    change(bill, "billing/fees.py", GOOD, BAD)
    monkeypatch.setattr(sessionmap, "MAX_CALLERS", 3)
    m = model(bill)
    assert len([n for n in m["nodes"] if n["kind"] == "caller"]) == 3 and m["truncated"] == 6


# ---- T9.2 HTML, Stop, command ----

def test_html_is_self_contained_and_has_every_node(bill):
    change(bill, "billing/fees.py", GOOD, BAD)
    cfg = cfgmod.load_config(str(bill))
    path = sessionmap.write(cfg, ledger.load(cfg.state_dir))
    html = path.read_text()
    assert path == bill / ".legacyguard/reports/sess1.html"
    assert "http://" not in html and "https://" not in html and "<link" not in html and " src=" not in html
    for n in model(bill)["nodes"]:
        assert n["id"] in html
    assert "prefers-color-scheme:dark" in html and "matched by name only" in html
    assert not __import__("re").search(r"\bsafe\b", html.lower())
    assert "score" not in html.lower()


def test_repo_text_cannot_break_out_of_the_page(bill):
    change(bill, "billing/fees.py", GOOD, BAD)
    cfg = cfgmod.load_config(str(bill))
    with ledger.locked(cfg.state_dir) as d:
        d["findings"][0]["evidence"] = "</script><script>alert(1)</script>"
        d["session_id"] = "<b>x</b>"
    html = sessionmap.render_html(sessionmap.build(cfg, ledger.load(cfg.state_dir)))
    assert "<script>alert(1)" not in html and "<b>x</b>" not in html


def stop(repo, active=True):
    r = run_script("stop_audit", {"cwd": str(repo), "session_id": "sess1", "hook_event_name": "Stop", "stop_hook_active": active})
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout) if r.stdout else {}


def test_stop_writes_the_map_next_to_the_report(bill):
    change(bill, "billing/fees.py", GOOD, BAD)
    out = stop(bill)
    reports = bill / ".legacyguard/reports"
    assert (reports / "sess1.md").exists() and (reports / "sess1.html").exists()
    assert "Map: " in out["systemMessage"] and "sess1.html" in out["systemMessage"]
    status = git(bill, "status", "--short", "--untracked-files=all")
    assert all(l.endswith("billing/fees.py") or ".legacyguard/" in l for l in status.splitlines()), status


def test_a_map_failure_never_costs_the_report(bill, monkeypatch):
    import _common  # noqa: F401
    import stop_audit
    change(bill, "billing/fees.py", GOOD, BAD)

    def boom(*a, **k):
        raise RuntimeError("map broke")
    monkeypatch.setattr(sessionmap, "build", boom)
    out = stop_audit.handle({"cwd": str(bill), "session_id": "sess1", "stop_hook_active": True})
    assert "Report: " in out["systemMessage"] and "Map: " not in out["systemMessage"]
    assert (bill / ".legacyguard/reports/sess1.md").exists()
    assert "map broke" in (bill / ".legacyguard/guard.log").read_text()


def test_stop_stays_quick_with_the_map(bill):
    change(bill, "billing/fees.py", GOOD, BAD)
    t = time.time()
    stop(bill)
    assert time.time() - t < 3


def test_map_command(bill):
    change(bill, "billing/fees.py", GOOD, BAD)
    r = subprocess.run([sys.executable, str(PLUGIN / "scripts/lg.py"), "map"], cwd=bill, capture_output=True, text=True, env={**os.environ, "CLAUDE_PROJECT_DIR": str(bill)})
    assert r.returncode == 0 and ".legacyguard/reports/sess1.html" in r.stdout
    assert (bill / ".legacyguard/reports/sess1.html").exists()


def test_map_skill_is_wired():
    text = (PLUGIN / "skills/map/SKILL.md").read_text()
    assert 'lg.py" --skill map' in text and "disable-model-invocation: true" in text


# ---- FR-31 story ----

def test_story_tells_asked_broke_fixed(bill):
    from guardlib import report
    run_script("prompt_context", {"cwd": str(bill), "session_id": "sess1", "prompt": "Simplify the late fee calculation"})
    change(bill, "billing/fees.py", GOOD, BAD)
    cfg = cfgmod.load_config(str(bill))
    steps = report.story(ledger.load(cfg.state_dir))
    assert [s["kind"] for s in steps] == ["asked", "broke", "open"]
    assert steps[0]["text"] == "Simplify the late fee calculation"
    assert '`compute_late_fee(balance=Decimal("40.20"), rate=Decimal("0.025"))` gave `1.01` before the edit and `1.00` after it' in steps[1]["text"]
    change(bill, "billing/fees.py", BAD, GOOD)
    steps = report.story(ledger.load(cfg.state_dir))
    assert [s["kind"] for s in steps] == ["asked", "broke", "fixed"]
    assert "ran it again" in steps[2]["text"] and "inputs compared" in steps[2]["text"]


def test_story_covers_unchecked_checked_and_asked_you(bill):
    from guardlib import report
    change(bill, "billing/tax.py", 'return Decimal("0.00")', 'return Decimal("0.00") + 0')
    change(bill, "reports/aging.py", '"""Bucket and projected late fee for one invoice, read from the live database."""', '"""Bucket."""')
    r = run_script("pre_edit", {"cwd": str(bill), "session_id": "sess1", "tool_name": "Edit", "tool_input": {
        "file_path": str(bill / "billing/api/schemas.py"), "old_string": "    currency: str\n    status: str\n", "new_string": "    status: str\n"}})
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "ask"
    stop(bill)
    cfg = cfgmod.load_config(str(bill))
    kinds = [s["kind"] for s in report.story(ledger.load(cfg.state_dir))]
    assert kinds == ["checked", "unchecked", "asked_you"]
    md = (bill / ".legacyguard/reports/sess1.md").read_text()
    assert "## What happened" in md and "**Not checked:**" in md and "**Asked you:**" in md and "the edit did not happen" in md
    html = (bill / ".legacyguard/reports/sess1.html").read_text()
    assert '"story"' in html and "What happened" in html


def test_story_never_says_safe_and_escapes_prompt(bill):
    from guardlib import report
    run_script("prompt_context", {"cwd": str(bill), "session_id": "sess1", "prompt": "<img src=x onerror=alert(1)> | fix it"})
    change(bill, "billing/fees.py", GOOD, BAD)
    cfg = cfgmod.load_config(str(bill))
    data = ledger.load(cfg.state_dir)
    text = " ".join(s["text"] for s in report.story(data))
    assert " safe" not in text.lower()
    html = sessionmap.render_html(sessionmap.build(cfg, data))
    assert "<img src=x" not in html
