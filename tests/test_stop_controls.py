"""T6.1 to T6.5: Stop audit, report, waive, mode, pin, status, remaining MCP tools."""
import json
import os
import shutil
import subprocess
import sys

import pytest

from conftest import PLUGIN, REPO, git, run_script
from guardlib import config as cfgmod, ledger, report, waivers

sys.path.insert(0, str(REPO / "demo"))
import build_billing_repo as builder  # noqa: E402

GOOD = "fee = fee.quantize(CENT, ROUND_HALF_UP)"
BAD = "fee = round(fee, 2)"
DROP = ("billing/api/schemas.py", "    currency: str\n    status: str\n", "    status: str\n")


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


def stop(repo, active=False):
    r = run_script("stop_audit", {"cwd": str(repo), "session_id": "sess1", "hook_event_name": "Stop", "stop_hook_active": active, "last_assistant_message": "done"})
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout) if r.stdout else {}


def bash_edit(repo, rel, old, new):
    p = repo / rel
    text = p.read_text()
    assert old in text
    p.write_text(text.replace(old, new))


def post(repo, rel):
    return run_script("post_edit", {"cwd": str(repo), "session_id": "sess1", "tool_name": "Edit", "tool_input": {"file_path": str(repo / rel)}})


def state(repo):
    return ledger.load(cfgmod.load_config(str(repo)).state_dir)


def lg(repo, *args):
    return subprocess.run([sys.executable, str(PLUGIN / "scripts" / "lg.py"), *args], cwd=repo, capture_output=True, text=True,
                          env={**os.environ, "CLAUDE_PROJECT_DIR": str(repo)}, timeout=120)


# ---- T6.1 stop audit ----

def test_clean_session_stops_with_report(bill):
    out = stop(bill)
    assert "decision" not in out and "Prompts 0 of 3" in out["systemMessage"]
    assert list((bill / ".legacyguard/reports").glob("*.md"))


def test_bash_contract_change_caught_block_once_never_twice(bill):
    bash_edit(bill, *DROP)  # no hooks fired for this: it was a shell edit
    first = stop(bill, active=False)
    assert first["decision"] == "block" and "InvoiceOut.currency" in first["reason"] and "session audit" in first["reason"]
    second = stop(bill, active=True)
    assert "decision" not in second and "1 confirmed failure" in second["systemMessage"]


def test_same_findings_do_not_block_on_a_later_turn(bill):
    bash_edit(bill, *DROP)
    assert stop(bill)["decision"] == "block"
    assert "decision" not in stop(bill, active=False), "each finding blocks at most once per session"


def test_bash_rounding_change_gets_a_counterexample_at_stop(bill):
    bash_edit(bill, "billing/fees.py", GOOD, BAD)
    out = stop(bill)
    assert out["decision"] == "block"
    assert 'compute_late_fee(balance=Decimal("40.20"), rate=Decimal("0.025")) before 1.01 after 1.00' in out["reason"]


def test_stop_does_not_rerun_what_post_edit_already_checked(bill, monkeypatch):
    bash_edit(bill, "billing/tax.py", 'return Decimal("0.00")', 'return Decimal("0.00") + 0')
    assert post(bill, "billing/tax.py").returncode == 0
    before = [f["id"] for f in state(bill)["findings"]]
    stop(bill)
    assert [f["id"] for f in state(bill)["findings"]] == before


def test_stale_callers_listed_when_signature_changes(bill):
    bash_edit(bill, "billing/fees.py", "def grace_days(tier: str) -> int:", "def grace_days(tier: str, extra: int) -> int:")
    stop(bill)
    stop(bill, active=True)
    f = [x for x in state(bill)["findings"] if x["kind"] == "stale_callers"][0]
    assert f["status"] == ledger.RISK
    assert "projected_fee (jobs/close_month.py)" in f["evidence"]


def test_test_edited_with_its_code_is_reported(bill):
    bash_edit(bill, "billing/tax.py", 'EXEMPT_TIERS = {"government"}', 'EXEMPT_TIERS = {"government", "x"}')
    bash_edit(bill, "tests/test_money_tax_discounts.py", 'assert tax.compute_tax(D("100.00"), "MS") == D("7.00")', 'assert tax.compute_tax(D("100.00"), "MS") == D("7.0")')
    stop(bill)
    assert any(f["kind"] == "test_edited_with_code" and f["status"] == ledger.RISK for f in state(bill)["findings"])


def test_rejected_edit_is_not_counted_as_landed(bill):
    r = run_script("pre_edit", {"cwd": str(bill), "session_id": "sess1", "tool_name": "Edit",
                                "tool_input": {"file_path": str(bill / DROP[0]), "old_string": DROP[1], "new_string": DROP[2]}})
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "ask"
    out = stop(bill)  # the edit was rejected, so the working tree is unchanged
    assert "decision" not in out
    f = state(bill)["findings"][0]
    assert f["state"] == "not_applied" and f["status"] == ledger.FAILURE
    assert "edit did not land" in (bill / ".legacyguard/reports/sess1.md").read_text()


def test_deleted_assertion_appears_in_report(bill):
    old = '    assert fees.capped_fee(D("5.00"), D("100.00")) == D("5.00")\n'
    r = run_script("pre_edit", {"cwd": str(bill), "session_id": "sess1", "tool_name": "Edit",
                                "tool_input": {"file_path": str(bill / "tests/test_fees.py"), "old_string": old, "new_string": ""}})
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "ask"
    bash_edit(bill, "tests/test_fees.py", old, "")
    post(bill, "tests/test_fees.py")
    stop(bill)
    assert "assertion removed from test_cap_limits_fee" in (bill / ".legacyguard/reports/sess1.md").read_text()


def test_frozen_file_changed_by_shell_is_caught(bill):
    bash_edit(bill, "legacy/ledger_v1.py", "def post_entry(", "def record_entry(")
    out = stop(bill)
    assert out["decision"] == "block" and "frozen file" in out["reason"]


def test_budget_overflow_finding_reaches_report_without_a_block(bill):
    cfg = cfgmod.load_config(str(bill))
    with ledger.locked(cfg.state_dir) as d:
        d["prompts_used"] = 3
    r = run_script("pre_edit", {"cwd": str(bill), "session_id": "sess1", "tool_name": "Edit",
                                "tool_input": {"file_path": str(bill / DROP[0]), "old_string": DROP[1], "new_string": DROP[2]}})
    assert "permissionDecision" not in json.loads(r.stdout)["hookSpecificOutput"]
    bash_edit(bill, *DROP)
    post(bill, DROP[0])
    assert "decision" not in stop(bill)
    text = (bill / ".legacyguard/reports/sess1.md").read_text()
    assert "InvoiceOut.currency" in text and "prompt budget used up" in text and "3 of 3" in text


def test_stop_with_no_config_is_silent(tmp_path):
    assert stop(tmp_path) == {}


# ---- T6.2 report ----

def test_report_contents(bill):
    bash_edit(bill, "billing/fees.py", GOOD, BAD)
    assert post(bill, "billing/fees.py").returncode == 2
    bash_edit(bill, "billing/fees.py", BAD, GOOD)
    assert post(bill, "billing/fees.py").returncode == 0
    bash_edit(bill, "reports/aging.py", "def bucket_name(days):", "def bucket_name(days):  # x")
    assert post(bill, "reports/aging.py").returncode == 0
    bash_edit(bill, "reports/aging.py", '"""Bucket and projected late fee for one invoice, read from the live database."""', '"""Bucket."""')
    assert post(bill, "reports/aging.py").returncode == 0
    out = stop(bill)
    text = (bill / ".legacyguard/reports/sess1.md").read_text()
    print(text)
    assert "Prompts used **0 of 3**" in text and "Claude wake-ups **1**" in text
    assert ledger.VERIFIED in text and ledger.DIFFERENCE in text and "turned back" in text
    assert ledger.UNTESTED in text and "database" in text
    assert "/legacyguard:pin LG-1" in text
    assert "not side effects" in text
    assert " safe" not in text.lower()
    assert "1 turned back" in out["systemMessage"]
    assert len(text.splitlines()) < 30


def test_every_non_pass_finding_has_input_or_reason(bill):
    bash_edit(bill, "billing/fees.py", GOOD, BAD)
    post(bill, "billing/fees.py")
    bash_edit(bill, "billing/invoices.py", '"""Add the late fee for an overdue invoice, once. Returns the fee added."""', '"""Add."""')
    post(bill, "billing/invoices.py")
    stop(bill, active=True)
    for f in state(bill)["findings"]:
        assert f["evidence"], f
        if f["status"] == ledger.UNTESTED:
            assert "untested because" in f["evidence"]
        if f["status"] == ledger.DIFFERENCE:
            assert "before" in f["evidence"] and "after" in f["evidence"]


def test_report_has_no_environment_values(bill, monkeypatch):
    bash_edit(bill, "billing/fees.py", GOOD, BAD)
    post(bill, "billing/fees.py")
    r = run_script("stop_audit", {"cwd": str(bill), "session_id": "sess1", "stop_hook_active": True}, env={"ANTHROPIC_API_KEY": "sekret-value"})
    assert r.returncode == 0
    assert "sekret-value" not in (bill / ".legacyguard/reports/sess1.md").read_text()


# ---- T6.3 waive and mode ----

def test_waive_silent_until_code_hash_changes(bill):
    bash_edit(bill, "billing/fees.py", GOOD, BAD)
    assert post(bill, "billing/fees.py").returncode == 2
    fid = state(bill)["findings"][0]["id"]
    r = lg(bill, "waive", fid, "finance asked for this")
    assert r.returncode == 0 and "Waived" in r.stdout
    w = json.loads((bill / ".legacyguard/waivers.json").read_text())[0]
    assert set(w) >= {"id", "reason", "file", "symbol", "code_hash", "date"} and w["reason"] == "finance asked for this"
    assert "decision" not in stop(bill), "waived findings do not block"
    assert post(bill, "billing/fees.py").returncode == 0
    bash_edit(bill, "billing/fees.py", BAD, 'fee = round(fee, 3)')
    assert post(bill, "billing/fees.py").returncode == 2, "changed code wakes again"


def test_waive_requires_reason_and_known_id(bill):
    assert lg(bill, "waive", "LG-99", "x").returncode != 0
    bash_edit(bill, "billing/fees.py", GOOD, BAD)
    post(bill, "billing/fees.py")
    assert lg(bill, "waive", "LG-1").returncode != 0
    assert lg(bill, "waive", "LG-1", "   ").returncode != 0


def test_verified_finding_cannot_be_waived(bill):
    bash_edit(bill, "billing/tax.py", 'return Decimal("0.00")', 'return Decimal("0.00") + 0')
    post(bill, "billing/tax.py")
    fid = state(bill)["findings"][0]["id"]
    assert lg(bill, "waive", fid, "x").returncode != 0


def test_mode_command_changes_next_decision_and_keeps_the_rest(bill):
    assert lg(bill, "mode", "strict").returncode == 0
    text = (bill / ".legacyguard/config.yaml").read_text()
    assert "mode: strict" in text and "frozen:" in text
    r = run_script("pre_edit", {"cwd": str(bill), "session_id": "sess1", "tool_name": "Edit",
                                "tool_input": {"file_path": str(bill / DROP[0]), "old_string": DROP[1], "new_string": DROP[2]}})
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert lg(bill, "mode", "sideways").returncode != 0


# ---- T6.4 pin ----

def test_pin_fails_on_bad_version_passes_on_good(bill):
    bash_edit(bill, "billing/fees.py", GOOD, BAD)
    assert post(bill, "billing/fees.py").returncode == 2
    fid = state(bill)["findings"][0]["id"]
    r = lg(bill, "pin", fid)
    assert r.returncode == 0, r.stderr
    test = bill / "tests/legacyguard" / f"test_pinned_{fid.replace('-', '_')}.py"
    assert test.exists()
    py = str(bill / ".venv/bin/python")
    env = {"PATH": os.environ["PATH"], "PYTHONDONTWRITEBYTECODE": "1"}
    bad = subprocess.run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(test)], cwd=bill, capture_output=True, text=True, env=env)
    assert bad.returncode == 1, bad.stdout
    bash_edit(bill, "billing/fees.py", BAD, GOOD)
    good = subprocess.run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(test)], cwd=bill, capture_output=True, text=True, env=env)
    assert good.returncode == 0, good.stdout


def test_nothing_is_written_outside_state_dir_without_pin(bill):
    bash_edit(bill, "billing/fees.py", GOOD, BAD)
    post(bill, "billing/fees.py")
    stop(bill, active=True)
    assert not (bill / "tests/legacyguard").exists()
    status = git(bill, "status", "--short", "--untracked-files=all")
    assert all(l.endswith("billing/fees.py") or ".legacyguard/" in l for l in status.splitlines()), status


def test_pin_rejects_findings_without_counterexamples(bill):
    assert lg(bill, "pin", "LG-99").returncode != 0
    bash_edit(bill, "billing/tax.py", 'return Decimal("0.00")', 'return Decimal("0.00") + 0')
    post(bill, "billing/tax.py")
    assert lg(bill, "pin", state(bill)["findings"][0]["id"]).returncode != 0


def test_pin_for_exception_counterexample(repo):
    (repo / ".legacyguard/config.yaml").write_text(f"scope: .\npython: {sys.executable}\n")
    (repo / "m.py").write_text('def f(n: int):\n    if n < 0:\n        raise ValueError("negative")\n    return n\n')
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "m")
    assert run_script("session_start", {"cwd": str(repo), "session_id": "s", "source": "startup"}).returncode == 0
    (repo / "m.py").write_text('def f(n: int):\n    return n\n')
    assert run_script("post_edit", {"cwd": str(repo), "session_id": "s", "tool_name": "Edit", "tool_input": {"file_path": str(repo / "m.py")}}).returncode == 2
    fid = state(repo)["findings"][0]["id"]
    assert lg(repo, "pin", fid).returncode == 0
    text = (repo / f"tests/legacyguard/test_pinned_{fid.replace('-', '_')}.py").read_text()
    assert "pytest.raises" in text and "ValueError" in text


# ---- T6.5 status and MCP tools ----

def test_status_lists_findings_mode_prompts(bill):
    bash_edit(bill, "billing/fees.py", GOOD, BAD)
    post(bill, "billing/fees.py")
    out = lg(bill, "status").stdout
    assert "guarded" in out and "0 of 3" in out and ledger.DIFFERENCE in out and "compute_late_fee" in out


def test_contract_and_diff_report_tools(bill):
    from test_mcp_server import call_tool
    bash_edit(bill, "billing/fees.py", GOOD, BAD)
    post(bill, "billing/fees.py")
    names, text = call_tool(bill, "contract", {"path": "openapi.yaml"})
    assert set(names) == {"impact", "contract", "diff_report"}
    assert "field:InvoiceOut.currency" in text
    _, text = call_tool(bill, "contract", {"path": "migrations/"})
    assert "column:invoices.currency" in text
    _, text = call_tool(bill, "diff_report", {"function": "compute_late_fee"})
    assert ledger.DIFFERENCE in text and "before 1.01" in text
    _, text = call_tool(bill, "diff_report", {"function": "nothing_here"})
    assert "no behavioral diff" in text


def test_skills_for_developer_actions_cannot_be_invoked_by_claude():
    for name in ("waive", "pin", "mode", "index"):
        assert "disable-model-invocation: true" in (PLUGIN / "skills" / name / "SKILL.md").read_text()
