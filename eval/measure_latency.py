#!/usr/bin/env python3
"""Measure real hook start-to-finish time on billing-api, as Claude Code starts them: python3 re-exec into the guard's venv (NFR-03)."""
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "demo"))
import build_billing_repo as builder  # noqa: E402

SCRIPTS = ROOT / "legacyguard" / "scripts"
RUNS = 7


def timed(script, event, env):
    t = time.perf_counter()
    r = subprocess.run(["python3", str(SCRIPTS / script)], input=json.dumps(event), capture_output=True, text=True, env=env)
    return time.perf_counter() - t, r


def main():
    data = Path(os.environ.get("LG_DATA") or (Path.home() / ".claude/plugins/data/legacyguard-inline"))
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "billing-api"
        builder.build(repo)
        env = {**os.environ, "CLAUDE_PLUGIN_DATA": str(data), "CLAUDE_PROJECT_DIR": str(repo)}
        subprocess.run(["python3", str(SCRIPTS / "lg.py"), "index"], cwd=repo, env=env, check=True, capture_output=True)
        timed("session_start.py", {"cwd": str(repo), "session_id": "m", "source": "startup"}, env)
        edit = {"cwd": str(repo), "session_id": "m", "tool_name": "Edit", "tool_input": {"file_path": str(repo / "billing/api/schemas.py"), "old_string": "    currency: str\n    status: str\n", "new_string": "    status: str\n"}}
        plain = {"cwd": str(repo), "session_id": "m", "tool_name": "Edit", "tool_input": {"file_path": str(repo / "billing/fees.py"), "old_string": "fee = fee.quantize(CENT, ROUND_HALF_UP)", "new_string": "fee = round(fee, 2)"}}
        prompt = {"cwd": str(repo), "session_id": "m", "prompt": "Simplify the late fee calculation in billing/fees.py"}
        out = {}
        for name, script, event in (("PreToolUse contract break", "pre_edit.py", edit), ("PreToolUse risk context", "pre_edit.py", plain), ("UserPromptSubmit", "prompt_context.py", prompt)):
            times = []
            for _ in range(RUNS):
                t, r = timed(script, event, env)
                assert r.returncode == 0, r.stderr
                times.append(t)
            out[name] = {"median_s": round(statistics.median(times), 3), "max_s": round(max(times), 3), "runs": RUNS}
        print(json.dumps(out, indent=1))
        (ROOT / "eval/results/latency.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
