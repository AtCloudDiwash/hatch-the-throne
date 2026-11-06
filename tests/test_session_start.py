"""T1.4 and T4.1: SessionStart."""
import json


def out(result):
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout) if result.stdout else {}


def test_folder_that_is_not_a_python_repo_is_left_alone(tmp_path, hook):
    """The plugin is installed for every session, so a folder it does not guard gets no message and no files."""
    o = out(hook("session_start", {"cwd": str(tmp_path), "session_id": "s", "source": "startup"}))
    assert o == {} and not (tmp_path / ".legacyguard").exists()


def test_invalid_config_gives_parse_error_and_does_not_block(repo, hook):
    (repo / ".legacyguard" / "config.yaml").write_text("mode: [unclosed")
    o = out(hook("session_start", {"cwd": str(repo), "session_id": "s", "source": "startup"}))
    assert "inactive" in o["systemMessage"].lower() and "hookSpecificOutput" not in o


def test_summary_in_context(repo, hook):
    o = out(hook("session_start", {"cwd": str(repo), "session_id": "s", "source": "startup"}))
    ctx = o["hookSpecificOutput"]["additionalContext"]
    assert "guarded" in ctx and "legacy/ledger.py" in ctx and "impact" in ctx
    assert len(ctx) <= 1500


def test_api_key_warning(repo, hook):
    o = out(hook("session_start", {"cwd": str(repo), "session_id": "s", "source": "startup"}, env={"ANTHROPIC_API_KEY": "x"}))
    assert "ANTHROPIC_API_KEY" in o["systemMessage"]


def test_no_warning_without_key(repo, hook):
    o = out(hook("session_start", {"cwd": str(repo), "session_id": "s", "source": "startup"}))
    assert "ANTHROPIC_API_KEY" not in o.get("systemMessage", "")


def test_bootstrap_failure_produces_manual_command(repo, tmp_path):
    """No network for install: a systemMessage with the manual command, guard inactive, exit 0."""
    import os
    import subprocess
    import sys
    from conftest import PLUGIN
    # Isolated interpreter with no third-party packages, and a pip index that cannot be reached.
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path), "CLAUDE_PLUGIN_DATA": str(tmp_path / "data"),
           "PIP_INDEX_URL": "http://127.0.0.1:9/simple", "PIP_RETRIES": "0", "PIP_NO_CACHE_DIR": "1", "PIP_TIMEOUT": "1"}
    venv = tmp_path / "bare"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True)
    r = subprocess.run([str(venv / "bin" / "python"), str(PLUGIN / "scripts" / "session_start.py")],
                       input=json.dumps({"cwd": str(repo), "session_id": "s", "source": "startup"}),
                       capture_output=True, text=True, env=env, timeout=200)
    assert r.returncode == 0
    msg = json.loads(r.stdout)["systemMessage"]
    assert "inactive" in msg and "pip install -r" in msg
