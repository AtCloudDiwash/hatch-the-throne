"""T5.6: PostToolUse wake-up on billing-api. E2E-1's exact counterexample, offline."""
import json
import shutil
import sys

import pytest

from conftest import REPO, run_script
from guardlib import config as cfgmod, ledger, waivers

sys.path.insert(0, str(REPO / "demo"))
import build_billing_repo as builder  # noqa: E402

GOOD = "fee = fee.quantize(CENT, ROUND_HALF_UP)"
BAD = "fee = round(fee, 2)"


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
    assert run_script("session_start", {"cwd": str(work), "session_id": "s", "source": "startup"}).returncode == 0
    return work


def replace(repo, rel, old, new):
    p = repo / rel
    text = p.read_text()
    assert old in text
    p.write_text(text.replace(old, new))
    return run_script("post_edit", {"cwd": str(repo), "session_id": "s", "tool_name": "Edit", "tool_input": {"file_path": str(p)}})


def state(repo):
    return ledger.load(cfgmod.load_config(str(repo)).state_dir)


def test_rounding_trap_wakes_with_exact_counterexample(bill):
    r = replace(bill, "billing/fees.py", GOOD, BAD)
    assert r.returncode == 2 and r.stdout == ""
    assert 'compute_late_fee(balance=Decimal("40.20"), rate=Decimal("0.025"))  before 1.01  after 1.00' in r.stderr
    assert len(r.stderr) <= 1500 and "safe" not in r.stderr.lower()
    d = state(bill)
    assert d["wakeups"] == 1
    f = [x for x in d["findings"] if x["kind"] == "behavior_difference"][0]
    assert f["status"] == ledger.DIFFERENCE and f["state"] == "open" and f["source"] == "diff"


def test_revert_records_verified_pass_by_execution(bill):
    assert replace(bill, "billing/fees.py", GOOD, BAD).returncode == 2
    r = replace(bill, "billing/fees.py", BAD, GOOD)
    assert r.returncode == 0 and r.stderr == ""
    d = state(bill)
    diff = [x for x in d["findings"] if x["kind"] == "behavior_difference"][0]
    ok = [x for x in d["findings"] if x["kind"] == "verified" and x["item"] == "compute_late_fee"][0]
    assert diff["state"] == "resolved" and ok["status"] == ledger.VERIFIED and ok["inputs_compared"] > 10
    assert d["wakeups"] == 1


def test_finding_reported_once_per_code_version(bill):
    assert replace(bill, "billing/fees.py", GOOD, BAD).returncode == 2
    p = bill / "billing/fees.py"
    r = run_script("post_edit", {"cwd": str(bill), "session_id": "s", "tool_name": "Edit", "tool_input": {"file_path": str(p)}})
    assert r.returncode == 0 and state(bill)["wakeups"] == 1


def test_a_different_bad_version_wakes_again(bill):
    assert replace(bill, "billing/fees.py", GOOD, BAD).returncode == 2
    assert replace(bill, "billing/fees.py", BAD, 'fee = fee.quantize(CENT, "ROUND_DOWN")').returncode == 2
    assert state(bill)["wakeups"] == 2


def test_waived_difference_stays_quiet_until_code_changes(bill):
    assert replace(bill, "billing/fees.py", GOOD, BAD).returncode == 2
    cfg = cfgmod.load_config(str(bill))
    f = [x for x in state(bill)["findings"] if x["kind"] == "behavior_difference"][0]
    waivers.add(cfg, f, "finance asked for banker's rounding")
    # Same code, new session: silent.
    assert run_script("session_start", {"cwd": str(bill), "session_id": "s2", "source": "startup"}).returncode == 0
    (bill / "billing/fees.py").write_text((bill / "billing/fees.py").read_text().replace(BAD, GOOD))
    assert run_script("session_start", {"cwd": str(bill), "session_id": "s3", "source": "startup"}).returncode == 0
    assert replace(bill, "billing/fees.py", GOOD, BAD).returncode == 0
    assert state(bill)["wakeups"] == 0
    # Changed code: asks again.
    assert replace(bill, "billing/fees.py", BAD, 'fee = fee.quantize(CENT, "ROUND_DOWN")').returncode == 2


def test_db_dependent_report_is_untested_never_verified(bill):
    r = replace(bill, "reports/aging.py", '"""Bucket and projected late fee for one invoice, read from the live database."""', '"""Bucket and fee."""\n    _ = 1')
    assert r.returncode == 0
    fs = [x for x in state(bill)["findings"] if x["item"] == "aging_bucket"]
    assert fs and all(x["status"] == ledger.UNTESTED for x in fs)
    assert "database" in fs[0]["evidence"]


def test_conn_taking_function_is_untested(bill):
    r = replace(bill, "billing/invoices.py", '"""Add the late fee for an overdue invoice, once. Returns the fee added."""', '"""Add the late fee."""')
    assert r.returncode == 0
    f = [x for x in state(bill)["findings"] if x["item"] == "accrue_late_fee"][0]
    assert f["status"] == ledger.UNTESTED and "conn" in f["evidence"]


def test_requested_rate_change_is_flagged_as_difference_only(bill):
    r = replace(bill, "billing/fees.py", 'DEFAULT_LATE_RATE = Decimal("0.025")', 'DEFAULT_LATE_RATE = Decimal("0.03")')
    assert r.returncode == 2 and "late_rate_for" in r.stderr
    assert "intent" in r.stderr.lower() or "intended" in r.stderr.lower()
    f = [x for x in state(bill)["findings"] if x["kind"] == "behavior_difference"][0]
    assert f["status"] == ledger.DIFFERENCE, "no automatic 'requested' label (D-024)"


def test_test_files_are_not_diffed(bill):
    r = replace(bill, "tests/test_fees.py", 'assert fees.grace_days("standard") == 0', 'assert fees.grace_days("standard") == 0  # ok')
    assert r.returncode == 0 and state(bill)["findings"] == []


def test_stale_result_is_dropped_when_a_newer_edit_landed(bill, monkeypatch):
    import _common  # noqa: F401
    from guardlib import engine, virtual
    import post_edit
    from runner import diff as differ
    p = bill / "billing/fees.py"
    p.write_text(p.read_text().replace(GOOD, BAD))
    real_run = differ.run

    def run_then_edit(*a, **k):
        out = real_run(*a, **k)
        p.write_text(p.read_text().replace(BAD, GOOD))
        return out
    monkeypatch.setattr(differ, "run", run_then_edit)
    assert post_edit.handle({"cwd": str(bill), "session_id": "s", "tool_input": {"file_path": str(p)}}) is None
    assert state(bill)["wakeups"] == 0


def test_every_finding_has_exactly_one_known_status(bill):
    replace(bill, "billing/fees.py", GOOD, BAD)
    replace(bill, "reports/aging.py", "def bucket_name(days):", "def bucket_name(days):  # x")
    for f in state(bill)["findings"]:
        assert f["status"] in ledger.STATUSES and f["source"] in ledger.SOURCES
