"""T1.2: config parsing, fail-open, output shape, path normalization."""
import json
import subprocess
import sys

import pytest

from conftest import PLUGIN
from guardlib import config as cfg
from guardlib import paths


def write(repo, text):
    (repo / ".legacyguard" / "config.yaml").write_text(text)


def test_valid_config_merges_defaults(repo):
    write(repo, "scope: billing-api/\nmode: strict\ncontracts:\n  http: openapi.yaml\nbehavioral_diff:\n  max_inputs: 9\n")
    c = cfg.load_config(str(repo))
    assert c.mode == "strict" and c.behavioral_diff["max_inputs"] == 9 and c.behavioral_diff["timeout_s"] == 60
    assert c.contract_path("http") == "billing-api/openapi.yaml" and c.budget == 3


def test_missing_config(tmp_path):
    with pytest.raises(cfg.ConfigMissing):
        cfg.load_config(str(tmp_path))


@pytest.mark.parametrize("text", ["mode: [unclosed", "mode: sideways\n", "- a\n- b\n", "behavioral_diff:\n  network: open\n"])
def test_invalid_config(repo, text):
    write(repo, text)
    with pytest.raises(cfg.ConfigError):
        cfg.load_config(str(repo))


def test_mode_change_applies_on_next_call(repo):
    assert cfg.load_config(str(repo)).mode == "guarded"
    write(repo, "mode: advisory\n")
    assert cfg.load_config(str(repo)).mode == "advisory"


def test_target_python_prefers_config_then_venv(repo):
    (repo / "venv" / "bin").mkdir(parents=True)
    (repo / "venv" / "bin" / "python").write_text("")
    assert cfg.target_python(cfg.load_config(str(repo))).endswith("venv/bin/python")
    (repo / ".venv" / "bin").mkdir(parents=True)
    (repo / ".venv" / "bin" / "python").write_text("")
    assert cfg.target_python(cfg.load_config(str(repo))).endswith(".venv/bin/python")
    write(repo, "python: /opt/py/bin/python3\n")
    assert cfg.target_python(cfg.load_config(str(repo))) == "/opt/py/bin/python3"


def _run(code, stdin="{}"):
    script = f"import sys; sys.path.insert(0, {str(PLUGIN / 'scripts')!r}); import _common\n{code}\n"
    return subprocess.run([sys.executable, "-c", script], input=stdin, capture_output=True, text=True)


def test_fail_open_on_exception_exit0_no_stdout():
    r = _run("def h(e): raise ValueError('boom')\n_common.run_hook(h)")
    assert r.returncode == 0 and r.stdout == ""


def test_fail_open_logs_to_guard_log(repo):
    r = _run("def h(e): raise ValueError('boom')\n_common.run_hook(h)", json.dumps({"cwd": str(repo)}))
    assert r.returncode == 0 and r.stdout == ""
    assert "ValueError: boom" in (repo / ".legacyguard" / "guard.log").read_text()


def test_fail_open_on_bad_stdin():
    r = _run("_common.run_hook(lambda e: {'x': 1})", "not json")
    assert r.returncode == 0 and r.stdout == ""


def test_exactly_one_json_object_even_with_stray_prints():
    r = _run("def h(e):\n    print('stray')\n    return {'systemMessage': 'hi'}\n_common.run_hook(h)")
    assert r.returncode == 0 and json.loads(r.stdout) == {"systemMessage": "hi"}


def test_no_output_when_handler_returns_none():
    r = _run("_common.run_hook(lambda e: None)")
    assert r.returncode == 0 and r.stdout == ""


def test_wake_exits_2_with_stderr_and_clips():
    r = _run("def h(e): raise _common.Wake('x' * 5000)\n_common.run_hook(h)")
    assert r.returncode == 2 and r.stdout == "" and len(r.stderr) <= 1500


def test_additional_context_is_clipped():
    code = ("def h(e): return _common.hook_output('PreToolUse', context='y' * 5000)\n_common.run_hook(h)")
    out = json.loads(_run(code).stdout)
    assert len(out["hookSpecificOutput"]["additionalContext"]) <= 1500


def test_allow_never_sets_permission_decision():
    import _common
    out = _common.hook_output("PreToolUse", context="c")
    assert "permissionDecision" not in out["hookSpecificOutput"]
    assert _common.hook_output("PreToolUse") is None


@pytest.mark.parametrize("path,root,rel", [
    ("C:\\repo\\billing\\fees.py", "C:\\repo", "billing/fees.py"),
    ("c:\\repo\\legacy\\ledger.py", "C:/repo", "legacy/ledger.py"),
    ("D:\\other\\x.py", "C:\\repo", None),
])
def test_windows_paths(path, root, rel):
    assert paths.relative_to_root(path, root) == rel


def test_windows_paths_match_scope_and_frozen():
    rel = paths.relative_to_root("C:\\repo\\svc\\legacy\\ledger.py", "C:\\repo")
    assert paths.in_scope(rel, "svc/") and not paths.in_scope(rel, "other/")
    assert paths.matches_any(rel, ["svc\\legacy\\ledger.py"]) and paths.matches_any(rel, ["svc/legacy/*.py"])


def test_scope_dot_includes_everything():
    assert paths.in_scope("a/b.py", ".") and paths.in_scope("a/b.py", "./")
    assert not paths.in_scope(None, ".")
