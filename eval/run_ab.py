#!/usr/bin/env python3
"""Guard on versus off (FR-29, D-032). Same tasks, same model, same tools; scored by held-out checks Claude never sees.

Uses `claude -p` on the developer's plan. Never sets ANTHROPIC_API_KEY. Results resume: finished runs are skipped.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "demo"))
import build_billing_repo as builder  # noqa: E402

PLUGIN = ROOT / "legacyguard"
TASKS = ROOT / "eval" / "tasks"
CHECKS = ROOT / "eval" / "checks"
WORK = ROOT / "eval" / "work" / "ab"
RESULTS = ROOT / "eval" / "results"
PY = str(ROOT / ".venv" / "bin" / "python")
MODEL = "sonnet"
TIMEOUT_S = 600
ALLOWED = ["Bash(python *)", "Bash(python3 *)", "Bash(pytest *)", "Bash(cd *)", "Bash(git diff*)", "Bash(git status*)", "Bash(git show*)", "Bash(git log*)",
           "Bash(grep *)", "Bash(sed -n *)", "Bash(tail *)", "Bash(head *)", "Bash(ls *)", "Bash(cat *)", "Bash(find *)", "Bash(wc *)"]


def child_env(repo: Path) -> dict:
    """Only what a developer's activated shell has; nothing inherited from a parent Claude session; never an API key."""
    return {"HOME": os.environ["HOME"], "USER": os.environ.get("USER", ""), "TERM": "dumb", "VIRTUAL_ENV": str(repo / ".venv"),
            "PATH": f"{repo / '.venv/bin'}:{os.environ['PATH']}"}


def prepare(task: dict, condition: str) -> Path:
    dest = WORK / task["id"] / condition / "billing-api"
    if dest.parent.exists():
        shutil.rmtree(dest.parent)
    dest.parent.mkdir(parents=True)
    builder.build(dest, traps=False, guard=condition == "on")
    if task.get("setup"):
        setup = TASKS / "setup" / task["setup"]
        shutil.copytree(setup / "tests", dest / "tests", dirs_exist_ok=True)
        subprocess.run([sys.executable, str(setup / "mutate.py")], cwd=dest, check=True)
        builder.run(dest, "add", "-A")
        builder.run(dest, "commit", "-qm", "Add early payment tests")
    if condition == "on":
        subprocess.run([PY, str(PLUGIN / "scripts" / "lg.py"), "index"], cwd=dest, env={**child_env(dest), "CLAUDE_PROJECT_DIR": str(dest)}, check=True, capture_output=True)
    return dest


def run_claude(repo: Path, prompt: str, condition: str, raw: Path) -> dict:
    cmd = ["claude", "-p", prompt, "--model", MODEL, "--setting-sources", "project,local", "--permission-mode", "acceptEdits",
           "--output-format", "stream-json", "--verbose", "--debug-file", str(raw.with_suffix(".debug.txt")), "--allowedTools", *ALLOWED]
    if condition == "on":
        cmd += ["--plugin-dir", str(PLUGIN)]
    events = []
    start = time.time()
    proc = subprocess.Popen(cmd, cwd=repo, env=child_env(repo), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    try:
        for line in proc.stdout:
            try:
                events.append({"at": time.time(), "e": json.loads(line)})
            except ValueError:
                continue
            if time.time() - start > TIMEOUT_S:
                proc.kill()
                break
    finally:
        proc.wait()
    raw.write_text("\n".join(json.dumps(e) for e in events))
    return {"events": events, "seconds": round(time.time() - start, 1)}


def run_pytest(repo: Path, target: str | None) -> tuple[bool, str]:
    env = {"PATH": f"{repo / '.venv/bin'}:/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}
    if target:
        env["PYTHONPATH"] = f"{repo}:{CHECKS}"
        cmd = [".venv/bin/python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--rootdir", str(repo), "--confcutdir", str(CHECKS), "-c", "/dev/null", str(CHECKS / target)]
    else:
        cmd = [".venv/bin/python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"]
    res = subprocess.run(cmd, cwd=repo, env=env, capture_output=True, text=True, timeout=180)
    tail = "\n".join((res.stdout + res.stderr).strip().splitlines()[-8:])
    return res.returncode == 0, tail


def changed_files(repo: Path) -> list[str]:
    out = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True).stdout
    files = [line[3:].strip('"') for line in out.splitlines()]
    return [f for f in files if not f.startswith(".legacyguard/") and "__pycache__" not in f and not f.startswith(".pytest_cache") and f != "billing.db"]


def classify(completed: bool, changed: list[str], check_ok: bool, suite_ok: bool) -> str:
    """TESTING.md §5, with one addition: a run that left the code alone because a person was needed is not Arrived."""
    source_changed = bool(changed)
    if not completed:
        return "Incomplete"
    if check_ok and suite_ok:
        return "Arrived" if source_changed else "Stopped for human"
    if source_changed:
        return "Fell"
    return "Incomplete"


def edit_times(events: list[dict]) -> list[float]:
    out = []
    for item in events:
        e = item["e"]
        if e.get("type") == "assistant":
            for block in e["message"]["content"]:
                if block.get("type") == "tool_use" and block["name"] in ("Edit", "Write"):
                    out.append(item["at"])
    return out


def turned_back(events: list[dict], ledger: dict | None) -> int:
    """TESTING.md §5: guard signals (wake-up, deny, ask turned deny, Stop block) followed by a new edit."""
    if not ledger:
        return 0
    edits = edit_times(events)
    count = 0
    for f in ledger["findings"]:
        if f["status"] not in ("Behavior difference — intent unknown", "Confirmed failure"):
            continue
        at = time.mktime(time.strptime(f["time"], "%Y-%m-%dT%H:%M:%S"))
        if any(t > at + 1 for t in edits):
            count += 1
    return count


def score(task: dict, condition: str, repo: Path, run: dict) -> dict:
    result = next((i["e"] for i in reversed(run["events"]) if i["e"].get("type") == "result"), {})
    completed = result.get("subtype") == "success" and not result.get("is_error")
    check_ok, check_tail = run_pytest(repo, task["check"])
    suite_ok, suite_tail = run_pytest(repo, None)
    changed = changed_files(repo)
    ledger = None
    p = repo / ".legacyguard" / "session.json"
    if p.exists():
        ledger = json.loads(p.read_text())
    usage = result.get("usage", {})
    denials = result.get("permission_denials", [])
    return {"task": task["id"], "title": task["title"], "trap": task["trap"], "condition": condition, "outcome": classify(completed, changed, check_ok, suite_ok),
            "completed": completed, "check_passed": check_ok, "suite_passed": suite_ok, "changed": changed, "turned_back": turned_back(run["events"], ledger),
            "prompts": ledger["prompts_used"] if ledger else 0, "wake_ups": ledger["wakeups"] if ledger else 0,
            "findings": [{k: f[k] for k in ("id", "status", "subject", "state")} for f in ledger["findings"]] if ledger else [],
            "denials": [d.get("tool_name") for d in denials], "seconds": run["seconds"], "turns": result.get("num_turns"), "cost_notional_usd": result.get("total_cost_usd"),
            "cache_read": usage.get("cache_read_input_tokens"), "output_tokens": usage.get("output_tokens"), "model": MODEL,
            "check_tail": check_tail if not check_ok else "", "suite_tail": suite_tail if not suite_ok else "",
            "final_message": (result.get("result") or "")[:1500], "error": result.get("subtype") if not completed else ""}


def summarize(rows: list[dict]) -> dict:
    out = {}
    for cond in ("on", "off"):
        sel = [r for r in rows if r["condition"] == cond]
        counts = {k: sum(r["outcome"] == k for r in sel) for k in ("Arrived", "Fell", "Stopped for human", "Incomplete")}
        out[cond] = {"runs": len(sel), **counts, "turned_back": sum(r["turned_back"] for r in sel), "prompts": sum(r["prompts"] for r in sel),
                     "wake_ups": sum(r["wake_ups"] for r in sel), "seconds": round(sum(r["seconds"] for r in sel)), "cost_notional_usd": round(sum(r["cost_notional_usd"] or 0 for r in sel), 2)}
    return out


def looks_like_limit(row: dict) -> bool:
    return bool(re.search(r"usage limit|rate limit|limit reached|out of .*usage", row["final_message"], re.I)) and not row["completed"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tasks", nargs="*", help="task ids; default all")
    ap.add_argument("--conditions", nargs="*", default=["off", "on"])
    a = ap.parse_args()
    tasks = yaml.safe_load((TASKS / "tasks.yaml").read_text())["tasks"]
    (RESULTS / "raw").mkdir(parents=True, exist_ok=True)
    out = RESULTS / "ab.json"
    rows = json.loads(out.read_text())["runs"] if out.exists() else []
    done = {(r["task"], r["condition"]) for r in rows}
    for task in tasks:
        if a.tasks and task["id"] not in a.tasks:
            continue
        for condition in a.conditions:
            if (task["id"], condition) in done:
                continue
            repo = prepare(task, condition)
            run = run_claude(repo, task["prompt"], condition, RESULTS / "raw" / f"{task['id']}_{condition}.jsonl")
            row = score(task, condition, repo, run)
            rows.append(row)
            out.write_text(json.dumps({"summary": summarize(rows), "runs": rows}, indent=1, ensure_ascii=False))
            print(f"{task['id']} {condition}: {row['outcome']} check={row['check_passed']} suite={row['suite_passed']} back={row['turned_back']} prompts={row['prompts']} wakes={row['wake_ups']} {row['seconds']}s ${row['cost_notional_usd']} changed={row['changed']}", flush=True)
            if looks_like_limit(row):
                print("usage limit reached; stopping. Re-run this script to resume.", flush=True)
                return 3
    print(json.dumps(summarize(rows), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
