"""T7.1, T7.2: backtest harness on a small repo with known commits."""
import json
import sys

import pytest

from conftest import commit_all, git
from guardlib import backtest, config as cfgmod, ledger


@pytest.fixture
def hist(repo):
    (repo / ".legacyguard/config.yaml").write_text(f"scope: .\npython: {sys.executable}\ncontracts:\n  db: migrations/\nbehavioral_diff:\n  max_inputs: 30\n")
    (repo / "m.py").write_text("def f(n: int):\n    return n + 1\n\ndef g(n: int):\n    return n * 2\n")
    commit_all(repo, "base")
    (repo / "m.py").write_text("def f(n: int):\n    return n + 1  # comment only\n\ndef g(n: int):\n    return n * 2\n")
    commit_all(repo, "harmless")
    (repo / "m.py").write_text("def f(n: int):\n    return n + 1\n\ndef g(n: int):\n    return n * 3\n")
    commit_all(repo, "changes behavior")
    (repo / "tests").mkdir()
    (repo / "tests/test_m.py").write_text("def test_a():\n    assert 1 == 1\n    assert 2 == 2\n")
    commit_all(repo, "add test")
    (repo / "tests/test_m.py").write_text("def test_a():\n    assert 1 == 1\n")
    commit_all(repo, "weaken test")
    return repo


def test_replay_counts(hist, tmp_path):
    cfg = cfgmod.load_config(str(hist))
    r = backtest.replay(cfg, 10, ("",), {}, tmp_path / "r.json", log=lambda *_: None)
    s = r["summary"]
    assert s["edits"] == 4 and s["wake_ups"] == 1 and s["prompts"] == 1 and s["denies"] == 0
    assert s["prompt_rate_per_10_edits"] == 2.5 and s["wake_up_rate_per_20_edits"] == 5.0
    assert s["function_statuses"][ledger.VERIFIED] == 1 and s["function_statuses"][ledger.DIFFERENCE] == 1
    assert "lgbacktest" not in git(hist, "worktree", "list")


def test_replay_resumes_from_its_file(hist, tmp_path):
    cfg = cfgmod.load_config(str(hist))
    out = tmp_path / "r.json"
    first = backtest.replay(cfg, 10, ("",), {}, out, log=lambda *_: None)
    calls = []
    second = backtest.replay(cfg, 10, ("",), {}, out, log=calls.append)
    assert calls == [] and second["summary"] == first["summary"]


def test_planted_bugs(hist, tmp_path):
    cfg = cfgmod.load_config(str(hist))
    head = git(hist, "rev-parse", "HEAD").strip()
    bugs = tmp_path / "b.json"
    bugs.write_text(json.dumps({"base_commit": head, "bugs": [
        {"id": "B1", "file": "m.py", "old": "return n + 1", "new": "return n + 2", "what": "off by one"},
        {"id": "B2", "file": "m.py", "old": "NOT THERE", "new": "x", "what": "stale"}]}))
    r = backtest.planted(cfg, bugs, {}, tmp_path / "p.json", log=lambda *_: None)
    assert r["applied"] == 1 and r["catch_rate_proved_by_execution"] == 1.0
    assert r["bugs"][0]["functions"][0]["example"]["before"] != r["bugs"][0]["functions"][0]["example"]["after"]
    assert r["bugs"][1]["applied"] is False
    assert git(hist, "status", "--short", "m.py") == ""
