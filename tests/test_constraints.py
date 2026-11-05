"""CLAUDE.md non-negotiable constraints that can be checked by reading the code."""
import json
import re
from pathlib import Path

from conftest import PLUGIN, REPO

SOURCE = [p for p in PLUGIN.rglob("*") if p.suffix in (".py", ".json", ".md", ".txt") and "__pycache__" not in p.parts]


def test_no_anthropic_sdk_or_api_host_anywhere_in_the_guard():
    for path in SOURCE:
        text = path.read_text()
        assert not re.search(r"^\s*(import|from)\s+anthropic\b", text, re.M), path
        assert "api.anthropic.com" not in text, path
        assert "anthropic" not in (PLUGIN / "requirements.txt").read_text().lower()


def test_api_key_is_only_ever_checked_for_the_warning():
    hits = [p.name for p in SOURCE if p.suffix == ".py" and "ANTHROPIC_API_KEY" in p.read_text()]
    assert hits == ["session_start.py"], hits
    text = (PLUGIN / "scripts/session_start.py").read_text()
    assert len(re.findall(r'os\.environ\.get\("ANTHROPIC_API_KEY"\)', text)) == 1
    assert 'os.environ["ANTHROPIC_API_KEY"]' not in text


def test_guard_never_starts_a_model():
    for path in SOURCE:
        if path.suffix == ".py":
            assert not re.search(r"""\[\s*["']claude["']""", path.read_text()), path


def test_no_prompt_or_agent_hooks():
    hooks = json.loads((PLUGIN / "hooks/hooks.json").read_text())["hooks"]
    assert set(hooks) == {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"}
    for groups in hooks.values():
        for group in groups:
            for h in group["hooks"]:
                assert h["type"] == "command" and h["command"] == "python3" and h["args"][0].startswith("${CLAUDE_PLUGIN_ROOT}/")


def test_only_the_diff_hook_is_async_and_nothing_sets_on_failure():
    hooks = json.loads((PLUGIN / "hooks/hooks.json").read_text())["hooks"]
    assert hooks["PostToolUse"][0]["hooks"][0]["asyncRewake"] is True
    for name, groups in hooks.items():
        for group in groups:
            for h in group["hooks"]:
                assert "onFailure" not in h, "D-020: fail open"
                if name != "PostToolUse":
                    assert "asyncRewake" not in h and "async" not in h


def test_no_rejected_ideas_reintroduced():
    deps = (PLUGIN / "requirements.txt").read_text().lower()
    for word in ("chroma", "faiss", "sentence-transformers", "networkx", "openai"):
        assert word not in deps


def test_guard_text_never_claims_safe():
    for path in SOURCE:
        if path.suffix == ".py" and path.name != "lg_worker.py":
            for s in re.findall(r"""["']([^"'\n]*)["']""", path.read_text()):
                assert not re.search(r"\b(is|are|looks|change is) safe\b", s, re.I), (path, s)


def test_context_is_never_written_as_a_system_command():
    for name in ("pre_edit", "prompt_context", "post_edit", "stop_audit", "session_start"):
        assert "SYSTEM:" not in (PLUGIN / "scripts" / f"{name}.py").read_text()


def test_every_status_string_comes_from_the_five():
    from guardlib import ledger
    assert ledger.STATUSES == ("Verified pass", "Confirmed failure", "Behavior difference — intent unknown", "Potential risk (static only)", "Untested")
