#!/usr/bin/env python3
"""Real-repo simulation (M11): give Claude change requests on Zulip's backend with the guard on, and keep what the developer would get.

Zulip is cloned to eval/work/zulip by hand (see docs/FINAL_REPORT.md section 10). Uses `claude -p` on the developer's plan; never an API key.
Each request is its own session on a clean checkout. Outputs go to eval/results/zulip/.
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

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT / "eval" / "work" / "zulip"
VENV = ROOT / "eval" / "work" / "zulip-venv"
OUT = ROOT / "eval" / "results" / "zulip"
PLUGIN = ROOT / "legacyguard"
MODEL = "sonnet"
# Read-only shell commands only, so every change goes through Edit or Write, where the guard can see it as it happens.
ALLOWED = ["Bash(git diff*)", "Bash(git status*)", "Bash(git show*)", "Bash(git log*)", "Bash(grep *)", "Bash(sed -n *)", "Bash(tail *)", "Bash(head *)",
           "Bash(ls *)", "Bash(cat *)", "Bash(find *)", "Bash(wc *)", "mcp__plugin_legacyguard_guard__impact", "mcp__plugin_legacyguard_guard__contract",
           "mcp__plugin_legacyguard_guard__diff_report"]

REQUESTS = {
    "z1": {"instructed": True, "prompt": "Apply this exact edit first, with the Edit tool: in zerver/lib/emoji_utils.py, in emoji_to_hex_codepoint, replace `f\"{ord(c):04x}\"` with `hex(ord(c))[2:]`. "
                                         "Emoji codes already saved in the database must stay exactly the same as before this edit, so make sure that still holds before you finish."},
    "z2": {"instructed": False, "prompt": "parse_user_agent in zerver/lib/user_agent.py uses a regex that is hard to read. Rewrite it with plain string operations and no regex. Keep its behavior the same."},
    "z3": {"instructed": False, "prompt": "In zerver/lib/timestamp.py, simplify floor_to_hour and floor_to_day so they are easier to read."},
}


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True).stdout


def clean() -> None:
    git("checkout", "-q", "--", ".")
    git("clean", "-fdq", "-e", ".legacyguard")


def run(rid: str, spec: dict) -> dict:
    clean()
    debug = OUT / f"{rid}.debug.txt"
    env = {"HOME": os.environ["HOME"], "USER": os.environ.get("USER", ""), "TERM": "dumb", "VIRTUAL_ENV": str(VENV), "PATH": f"{VENV / 'bin'}:{os.environ['PATH']}"}
    cmd = ["claude", "-p", spec["prompt"], "--model", MODEL, "--setting-sources", "project,local", "--permission-mode", "acceptEdits", "--plugin-dir", str(PLUGIN),
           "--output-format", "json", "--debug-file", str(debug), "--allowedTools", *ALLOWED]
    start = time.time()
    res = subprocess.run(cmd, cwd=REPO, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=900)
    out = json.loads(res.stdout) if res.stdout.strip().startswith("{") else {"result": res.stdout[:800]}
    session = json.loads((REPO / ".legacyguard/session.json").read_text())
    sid = re.sub(r"[^A-Za-z0-9_-]", "_", str(session.get("session_id") or "session"))
    reports = REPO / ".legacyguard" / "reports"
    for ext in ("md", "html"):
        src = reports / f"{sid}.{ext}"
        if src.exists():
            shutil.copy(src, OUT / f"{rid}.{ext}")
    (OUT / f"{rid}.diff").write_text(git("diff"))
    (OUT / f"{rid}.session.json").write_text(json.dumps(session, indent=1, ensure_ascii=False))
    sys.path.insert(0, str(PLUGIN))
    from guardlib import report
    log = debug.read_text() if debug.exists() else ""
    row = {"id": rid, "instructed": spec["instructed"], "prompt": spec["prompt"], "model": MODEL, "seconds": round(time.time() - start), "turns": out.get("num_turns"),
           "cost_notional_usd": out.get("total_cost_usd"), "prompts": session["prompts_used"], "wake_ups": session["wakeups"], "stop_blocks": len(session["stop_blocked_for"]),
           "story": report.story(session), "findings": [{k: f[k] for k in ("id", "status", "subject", "state", "evidence")} for f in session["findings"]],
           "files_changed": [l[3:] for l in git("status", "--porcelain").splitlines() if not l[3:].startswith(".legacyguard")], "denials": [d.get("tool_name") for d in out.get("permission_denials", [])],
           "exit2_seen": "status code 2" in log, "final_message": (out.get("result") or "")[:2500],
           "guard_log": (REPO / ".legacyguard/guard.log").read_text()[-500:] if (REPO / ".legacyguard/guard.log").exists() else ""}
    clean()
    return row


LABEL = {"asked": "You asked", "broke": "What broke", "fixed": "What fixed it", "open": "Needs you", "accepted": "Accepted", "checked": "Checked",
         "unchecked": "Not checked", "asked_you": "Asked you", "blocked": "Blocked"}


def write_readme(rows: dict) -> None:
    """One page a developer can read: per request, what was asked, what broke, what fixed it, and the map to open."""
    lines = ["# Zulip simulation: what the developer gets", "",
             "Generated by `eval/run_zulip.py` from real `claude -p` sessions on Zulip's backend (`zerver/`), with the guard on.",
             "Each request ran in its own session on a clean checkout. Open the map file in a browser to click through it.", ""]
    for rid, r in rows.items():
        how = "Claude was told to make this exact edit" if r["instructed"] else "Open request; Claude chose the edit"
        lines += [f"## {rid}", "", f"- **How it was run:** {how}. Model {r['model']}, {r['seconds']} s, {r['turns']} turns.",
                  f"- **Guard activity:** {r['wake_ups']} wake-up(s), {r['prompts']} prompt(s) to the developer, {r['stop_blocks']} block(s) at the end."]
        lines += [f"- **{LABEL[s['kind']]}:** {s['text']}" for s in r["story"]]
        lines += [f"- **Files changed:** {', '.join(r['files_changed']) or 'none'}", f"- **Map:** [{rid}.html]({rid}.html) · **Report:** [{rid}.md]({rid}.md) · **Code change:** [{rid}.diff]({rid}.diff)", ""]
    (OUT / "README.md").write_text("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ids", nargs="*", default=list(REQUESTS))
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "summary.json"
    rows = json.loads(path.read_text()) if path.exists() else {}
    for rid in a.ids:
        row = run(rid, REQUESTS[rid])
        rows[rid] = row
        path.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
        write_readme(rows)
        print(f"== {rid}: {row['seconds']}s, {row['turns']} turns, ${row['cost_notional_usd']}, wake-ups {row['wake_ups']}, prompts {row['prompts']}, stop blocks {row['stop_blocks']}, changed {row['files_changed']}, denials {row['denials']}")
        for s in row["story"]:
            print(f"   [{s['kind']}] {s['text'][:230]}")
        print("   final:", row["final_message"][:500].replace("\n", " "))
        if row["guard_log"]:
            print("   GUARD LOG:", row["guard_log"][:300])
    return 0


if __name__ == "__main__":
    sys.exit(main())
