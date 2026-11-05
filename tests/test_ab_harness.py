"""T7.3: the A/B scoring logic, with no model use."""
import sys

import pytest

from conftest import REPO

sys.path.insert(0, str(REPO / "eval"))
import run_ab  # noqa: E402


@pytest.mark.parametrize("completed,changed,check,suite,expected", [
    (True, ["a.py"], True, True, "Arrived"),
    (True, ["a.py"], False, True, "Fell"),
    (True, ["a.py"], True, False, "Fell"),
    (True, [], True, True, "Stopped for human"),
    (True, [], False, True, "Incomplete"),
    (False, ["a.py"], True, True, "Incomplete"),
])
def test_classify(completed, changed, check, suite, expected):
    assert run_ab.classify(completed, changed, check, suite) == expected


def test_child_environment_never_has_an_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("CLAUDECODE", "1")
    env = run_ab.child_env(tmp_path)
    assert "ANTHROPIC_API_KEY" not in env and "CLAUDECODE" not in env and env["VIRTUAL_ENV"].endswith(".venv")


def test_turned_back_needs_a_later_edit():
    finding = {"status": "Behavior difference — intent unknown", "time": "2026-11-05T12:00:00"}
    import time
    at = time.mktime(time.strptime(finding["time"], "%Y-%m-%dT%H:%M:%S"))
    edit = {"at": at + 30, "e": {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Edit"}]}}}
    assert run_ab.turned_back([edit], {"findings": [finding]}) == 1
    earlier = {"at": at - 30, "e": edit["e"]}
    assert run_ab.turned_back([earlier], {"findings": [finding]}) == 0
    assert run_ab.turned_back([edit], None) == 0
    assert run_ab.turned_back([edit], {"findings": [{"status": "Verified pass", "time": finding["time"]}]}) == 0


def test_prepare_on_and_off(tmp_path, monkeypatch):
    monkeypatch.setattr(run_ab, "WORK", tmp_path)
    t = {"id": "t07", "setup": "t07"}
    on = run_ab.prepare(t, "on")
    off = run_ab.prepare(t, "off")
    assert (on / ".legacyguard/index.db").exists() and (on / ".legacyguard/harvest.json").exists()
    assert not (off / ".legacyguard").exists() and not (off / "TRAPS.md").exists() and not (on / "TRAPS.md").exists()
    assert (off / "tests/test_early_pay.py").exists() and "<= window_days" in (off / "billing/discounts.py").read_text()
    assert run_ab.changed_files(off) == []
    ok, _ = run_ab.run_pytest(off, None)
    assert ok is False, "t07 starts with a failing suite"
