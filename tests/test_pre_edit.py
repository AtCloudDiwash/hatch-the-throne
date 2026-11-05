"""T4.1 to T4.6: baseline, prompt context, virtual apply, symbol diff, checks, policy fixture table."""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import REPO, commit_all, git, run_script
from guardlib import baseline, checks, config as cfgmod, ledger, policy, symbol_diff, virtual, waivers

sys.path.insert(0, str(REPO / "demo"))
import build_billing_repo as builder  # noqa: E402


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
    return work


def start(repo, sid="s1", source="startup"):
    r = run_script("session_start", {"cwd": str(repo), "session_id": sid, "source": source})
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout) if r.stdout else {}


def pre(repo, tool, path, **tool_input):
    r = run_script("pre_edit", {"cwd": str(repo), "session_id": "s1", "hook_event_name": "PreToolUse", "tool_name": tool,
                                "tool_input": {"file_path": str(path), **tool_input}})
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout) if r.stdout else {}


def edit(repo, rel, old, new):
    return pre(repo, "Edit", repo / rel, old_string=old, new_string=new)


def decision(out):
    return out.get("hookSpecificOutput", {}).get("permissionDecision")


def context(out):
    return out.get("hookSpecificOutput", {}).get("additionalContext", "")


def set_mode(repo, mode):
    p = repo / ".legacyguard" / "config.yaml"
    p.write_text(p.read_text().replace("mode: guarded", f"mode: {mode}"))


DROP_FIELD = ("billing/api/schemas.py", "    currency: str\n    status: str\n", "    status: str\n")


# ---- T4.1 baseline ----

def test_baseline_worktree_at_head(repo):
    start(repo)
    cfg = cfgmod.load_config(str(repo))
    assert (repo / ".legacyguard/baseline/app.py").exists()
    head = git(repo, "rev-parse", "HEAD").strip()
    assert git(repo / ".legacyguard/baseline", "rev-parse", "HEAD").strip() == head
    d = ledger.load(cfg.state_dir)
    assert d["baseline_commit"] == head and d["session_id"] == "s1" and d["baseline_ok"]
    assert git(repo, "status", "--short").strip() == "?? .legacyguard/" or ".legacyguard/.gitignore" in git(repo, "status", "--short", "-uall")
    assert "baseline" not in git(repo, "status", "--short", "-uall")


def test_baseline_includes_dirty_and_untracked_files(repo):
    (repo / "app.py").write_text("def add(a, b):\n    return b + a  # dirty\n")
    (repo / "new.py").write_text("x = 1\n")
    start(repo)
    assert "# dirty" in (repo / ".legacyguard/baseline/app.py").read_text()
    assert (repo / ".legacyguard/baseline/new.py").exists()
    d = ledger.load(cfgmod.load_config(str(repo)).state_dir)
    assert set(d["dirty_files"]) == {"app.py", "new.py"}
    assert baseline.changed_files(cfgmod.load_config(str(repo))) == []


def test_baseline_recreated_each_session_and_ledger_reset(repo):
    start(repo)
    cfg = cfgmod.load_config(str(repo))
    with ledger.locked(cfg.state_dir) as d:
        d["prompts_used"] = 2
    (repo / "marker.py").write_text("y = 1\n")
    git(repo, "add", "marker.py")
    git(repo, "commit", "-qm", "m")
    start(repo, "s2")
    assert (repo / ".legacyguard/baseline/marker.py").exists()
    assert ledger.load(cfg.state_dir)["prompts_used"] == 0


def test_compact_keeps_baseline_and_ledger(repo):
    start(repo)
    cfg = cfgmod.load_config(str(repo))
    with ledger.locked(cfg.state_dir) as d:
        d["prompts_used"] = 2
    (repo / "app.py").write_text("def add(a, b):\n    return a - b\n")
    start(repo, "s1", "compact")
    assert ledger.load(cfg.state_dir)["prompts_used"] == 2
    assert baseline.changed_files(cfg) == ["app.py"]


def test_not_a_git_repo_gives_notice(tmp_path):
    (tmp_path / ".legacyguard").mkdir()
    (tmp_path / ".legacyguard/config.yaml").write_text("scope: .\n")
    out = start(tmp_path)
    assert "not a git repository" in out["systemMessage"]


# ---- T4.2 prompt context ----

def prompt(repo, text):
    t = time.time()
    r = run_script("prompt_context", {"cwd": str(repo), "session_id": "s1", "prompt": text})
    assert r.returncode == 0, r.stderr
    return (json.loads(r.stdout) if r.stdout else {}), time.time() - t


def test_prompt_naming_file_gets_callers_routes_tests(bill):
    start(bill)
    out, elapsed = prompt(bill, "Please clean up billing/fees.py")
    ctx = context(out)
    assert "compute_late_fee" in ctx and "[routes]" in ctx and "[tests]" in ctx
    assert len(ctx) <= 1500 and elapsed < 2
    assert "decision" not in out and "updatedPrompt" not in out


def test_prompt_words_find_function(bill):
    start(bill)
    out, _ = prompt(bill, "Simplify the late fee calculation")
    assert "compute_late_fee" in context(out)


def test_prompt_stored_and_unrelated_prompt_gets_nothing(bill):
    start(bill)
    out, _ = prompt(bill, "What time is it?")
    assert out == {}
    assert ledger.load(cfgmod.load_config(str(bill)).state_dir)["prompt_text"] == ["What time is it?"]


# ---- T4.3 virtual apply and symbol diff ----

def test_virtual_apply_cases():
    assert virtual.apply("Edit", {"old_string": "a", "new_string": "b"}, "xax") == "xbx"
    assert virtual.apply("Edit", {"old_string": "a", "new_string": "b"}, "aa") is None
    assert virtual.apply("Edit", {"old_string": "a", "new_string": "b", "replace_all": True}, "aa") == "bb"
    assert virtual.apply("Edit", {"old_string": "z", "new_string": "b"}, "aa") is None
    assert virtual.apply("Write", {"content": "new"}, None) == "new"
    assert virtual.apply("Edit", {"old_string": "a", "new_string": "b"}, None) is None


BEFORE = "def keep(a):\n    return a\n\ndef sig(a):\n    return a * 1\n\ndef gone(a):\n    return a * 2\n\ndef old_name(a):\n    return a * 3\n\ndef public(a):\n    return a * 4\n\ndef body(a):\n    return a * 5\n"


def kinds(before, after):
    return {c.qualname: c.kind for c in symbol_diff.diff(before, after)}


def test_identical_bodies_are_not_called_a_rename():
    k = kinds("def a(x):\n    return x\n\ndef b(x):\n    return x\n", "def c(x):\n    return x\n")
    assert sorted(k.values()) == ["added", "deleted", "deleted"]


def test_symbol_diff_kinds():
    after = BEFORE.replace("def sig(a)", "def sig(a, b)").replace("def gone(a):\n    return a * 2\n\n", "") \
        .replace("def old_name(a)", "def new_name(a)").replace("def public(a)", "def _public(a)") \
        .replace("return a * 5", "return a + 1") + "def added():\n    pass\n"
    k = kinds(BEFORE, after)
    assert k == {"sig": "signature_changed", "gone": "deleted", "old_name": "renamed", "public": "visibility_changed", "body": "body_changed", "added": "added"}
    assert "keep" not in k


# ---- T4.4 contract and test integrity ----

def test_dropped_response_field_asks(bill):
    start(bill)
    out = edit(bill, *DROP_FIELD)
    assert decision(out) == "ask"
    assert "InvoiceOut.currency" in out["hookSpecificOutput"]["permissionDecisionReason"]
    assert "InvoiceOut.currency" in context(out)


def test_dropped_key_in_serializer_asks(bill):
    start(bill)
    assert decision(edit(bill, "billing/api/invoices.py", '        "currency": invoice["currency"],\n', "")) == "ask"


def test_openapi_edit_asks(bill):
    start(bill)
    text = (bill / "openapi.yaml").read_text()
    new = text.replace("        currency:\n          type: string\n          title: Currency\n        status:", "        status:", 1)
    assert new != text
    out = pre(bill, "Write", bill / "openapi.yaml", content=new)
    assert decision(out) == "ask" and "currency" in context(out)


def test_route_removed_and_param_renamed(bill):
    start(bill)
    out = edit(bill, "billing/api/invoices.py", '@router.post("/{invoice_id}/void", response_model=schemas.InvoiceOut)\n', "")
    assert decision(out) == "ask" and "route removed" in context(out)
    out = edit(bill, "billing/api/reports.py", "def month_revenue(day: str,", "def month_revenue(when: str,")
    assert decision(out) == "ask" and "day" in context(out)


def test_new_migration_dropping_a_column_asks(bill):
    start(bill)
    out = pre(bill, "Write", bill / "migrations/007_drop.sql", content="ALTER TABLE invoices DROP COLUMN legacy_ref;\n")
    assert decision(out) == "ask" and "legacy_ref" in context(out)


def test_rewriting_a_migration_to_lose_a_column_asks(bill):
    start(bill)
    text = (bill / "migrations/002_invoices.sql").read_text()
    out = pre(bill, "Write", bill / "migrations/002_invoices.sql", content=text.replace("    currency TEXT NOT NULL DEFAULT 'USD',\n", ""))
    assert decision(out) == "ask" and "invoices.currency" in context(out)


def test_additive_migration_is_fine(bill):
    start(bill)
    assert decision(pre(bill, "Write", bill / "migrations/007_add.sql", content="ALTER TABLE invoices ADD COLUMN note TEXT;\n")) is None


def test_event_field_removed_or_retyped_asks(bill):
    start(bill)
    p = bill / "schemas/events/invoice_settled.json"
    doc = json.loads(p.read_text())
    gone = json.loads(json.dumps(doc))
    del gone["properties"]["late_fee"]
    assert decision(pre(bill, "Write", p, content=json.dumps(gone))) == "ask"
    retyped = json.loads(json.dumps(doc))
    retyped["properties"]["amount"]["type"] = "number"
    out = pre(bill, "Write", p, content=json.dumps(retyped))
    assert decision(out) == "ask" and "retyped" in context(out)


TEST_SRC = "def test_x():\n    r = f()\n    assert r == 3\n    assert r > 0\n\ndef test_y():\n    assert g() == 1\n"


def subjects(after):
    return [b.item.split(":")[0] for b in checks.check_test_file("tests/test_a.py", TEST_SRC, after)]


def test_test_integrity_unit():
    assert subjects(TEST_SRC) == []
    assert subjects("def test_x():\n    r = f()\n    assert r == 3\n    assert r > 0\n") == ["deleted"]
    assert subjects(TEST_SRC.replace("    assert r > 0\n", "")) == ["assertion_removed"]
    assert subjects(TEST_SRC.replace("assert r == 3", "assert r")) == ["assertion_weakened"]
    assert subjects(TEST_SRC.replace("def test_y", "@pytest.mark.skip\ndef test_y")) == ["disabled"]
    assert subjects(TEST_SRC.replace("assert r == 3", "assert r == 4")) == []
    assert subjects(TEST_SRC + "\ndef test_z():\n    assert h() == 2\n") == []


def test_removed_assertion_asks(bill):
    start(bill)
    out = edit(bill, "tests/test_fees.py", '    assert fees.capped_fee(D("5.00"), D("100.00")) == D("5.00")\n', "")
    assert decision(out) == "ask" and "assertion removed" in context(out)


def test_new_test_file_is_fine(bill):
    start(bill)
    assert pre(bill, "Write", bill / "tests/test_new.py", content="def test_a():\n    assert 1 == 1\n") == {}


# ---- T4.5 decision policy fixture table (TESTING.md §2) ----

@pytest.mark.parametrize("mode,used,waived,expected", [
    ("guarded", 0, False, "ask"), ("guarded", 3, False, "allow"), ("advisory", 0, False, "allow"),
    ("strict", 0, False, "deny"), ("strict", 0, True, "allow"), ("guarded", 0, True, "allow"),
])
def test_policy_table(mode, used, waived, expected):
    assert policy.contract_decision(mode, used, 3, waived).action == expected


def test_fixture_guarded_ask_has_reason_and_context(bill):
    start(bill)
    out = edit(bill, *DROP_FIELD)
    h = out["hookSpecificOutput"]
    assert h["permissionDecision"] == "ask" and h["permissionDecisionReason"] and h["additionalContext"]
    assert ledger.load(cfgmod.load_config(str(bill)).state_dir)["prompts_used"] == 1


def test_fixture_budget_used_up_allows_with_context_and_queues(bill):
    start(bill)
    cfg = cfgmod.load_config(str(bill))
    with ledger.locked(cfg.state_dir) as d:
        d["prompts_used"] = 3
    out = edit(bill, *DROP_FIELD)
    assert decision(out) is None and "prompt budget" in context(out)
    d = ledger.load(cfg.state_dir)
    assert d["prompts_used"] == 3
    assert d["findings"][0]["last_decision"] == "over_budget" and d["findings"][0]["status"] == ledger.FAILURE


def test_fourth_break_in_a_session_does_not_prompt(bill):
    start(bill)
    text = (bill / "billing/api/schemas.py").read_text()
    results = []
    for field in ("currency", "status", "balance", "paid"):
        # Each attempt drops a different published field from the same unchanged file.
        cut = text.replace(f"    {field}: str\n", "", 1)
        results.append(pre(bill, "Write", bill / "billing/api/schemas.py", content=cut))
    assert [decision(r) for r in results] == ["ask", "ask", "ask", None]
    cfg = cfgmod.load_config(str(bill))
    d = ledger.load(cfg.state_dir)
    assert d["prompts_used"] == 3
    assert any(f["last_decision"] == "over_budget" for f in d["findings"])


def test_fixture_advisory_allows_with_context(bill):
    start(bill)
    set_mode(bill, "advisory")
    out = edit(bill, *DROP_FIELD)
    assert decision(out) is None and "InvoiceOut.currency" in context(out)


def test_fixture_strict_denies_until_waived_same_hash(bill):
    start(bill)
    set_mode(bill, "strict")
    out = edit(bill, *DROP_FIELD)
    assert decision(out) == "deny" and "waive" in out["hookSpecificOutput"]["permissionDecisionReason"]
    cfg = cfgmod.load_config(str(bill))
    d = ledger.load(cfg.state_dir)
    waivers.add(cfg, d["findings"][0], "mobile no longer reads it")
    out = edit(bill, *DROP_FIELD)
    assert decision(out) is None and "InvoiceOut.currency" in context(out)


def test_waiver_stops_applying_when_code_changes(bill):
    start(bill)
    set_mode(bill, "strict")
    edit(bill, *DROP_FIELD)
    cfg = cfgmod.load_config(str(bill))
    waivers.add(cfg, ledger.load(cfg.state_dir)["findings"][0], "ok")
    text = (bill / "billing/api/schemas.py").read_text()
    changed = text.replace("    currency: str\n    status: str\n", "    status: str\n").replace("class CustomerIn", "# note\nclass CustomerIn")
    assert decision(pre(bill, "Write", bill / "billing/api/schemas.py", content=changed)) == "deny"


def test_fixture_many_callers_is_context_never_ask(bill):
    start(bill)
    out = edit(bill, "billing/dates.py", "    late = (parse_date(as_of) - parse_date(due_date)).days - grace\n",
               "    late = (parse_date(as_of) - parse_date(due_date)).days - grace  # noted\n")
    assert decision(out) is None and "many_callers" in context(out)
    assert ledger.load(cfgmod.load_config(str(bill)).state_dir)["prompts_used"] == 0


def test_fixture_no_risk_signals_no_output(bill):
    start(bill)
    assert edit(bill, "billing/tax.py", 'EXEMPT_TIERS = {"government"}', 'EXEMPT_TIERS = {"government", "charity"}') == {}


def test_risk_context_sent_once_per_symbol(bill):
    start(bill)
    args = ("billing/dates.py", "def days_overdue(due_date, as_of, grace=0):\n", "def days_overdue(due_date, as_of, grace=0):  # x\n")
    assert context(edit(bill, *args))
    assert context(edit(bill, *args)) == ""


# ---- T4.6 frozen and scope ----

@pytest.mark.parametrize("mode", ["guarded", "strict", "advisory"])
def test_frozen_denied_in_every_mode(bill, mode):
    start(bill)
    set_mode(bill, mode)
    out = edit(bill, "legacy/ledger_v1.py", "def post_entry(", "def record_entry(")
    assert decision(out) == "deny"
    assert "frozen" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_outside_scope_allowed_with_notice_once(repo, tmp_path):
    (repo / ".legacyguard/config.yaml").write_text("scope: svc/\nfrozen: []\n")
    (repo / "svc").mkdir()
    (repo / "docs.py").write_text("x = 1\n")
    start(repo)
    out = pre(repo, "Write", repo / "docs.py", content="x = 2\n")
    assert decision(out) is None and "outside the guarded scope" in out["systemMessage"]
    assert pre(repo, "Write", repo / "docs.py", content="x = 3\n") == {}


def test_guard_state_is_protected_in_every_mode(repo):
    start(repo)
    assert decision(pre(repo, "Write", repo / ".legacyguard/waivers.json", content="[]")) == "deny"
    assert decision(pre(repo, "Edit", repo / ".legacyguard/config.yaml", old_string="guarded", new_string="advisory")) == "deny"


def test_old_string_missing_allows_with_no_finding(repo):
    start(repo)
    assert edit(repo, "app.py", "not in the file", "x") == {}
    assert ledger.load(cfgmod.load_config(str(repo)).state_dir)["findings"] == []


def test_unparsable_new_code_gets_context(repo):
    start(repo)
    out = pre(repo, "Write", repo / "app.py", content="def broken(:\n")
    assert decision(out) is None and "does not parse" in context(out)


def test_invalid_config_never_blocks(repo):
    (repo / ".legacyguard/config.yaml").write_text("mode: [broken")
    assert pre(repo, "Write", repo / "legacy.py", content="x") == {}


def test_mode_change_applies_to_next_decision(bill):
    start(bill)
    assert decision(edit(bill, *DROP_FIELD)) == "ask"
    set_mode(bill, "strict")
    assert decision(edit(bill, *DROP_FIELD)) == "deny"


def test_pre_edit_is_fast(bill):
    start(bill)
    t = time.time()
    edit(bill, *DROP_FIELD)
    assert time.time() - t < 1.0
