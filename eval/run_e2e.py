#!/usr/bin/env python3
"""E2E-1 to E2E-7 from TESTING.md §4 through `claude -p`, against generated copies of billing-api. E2E-8 is offline by design."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import run_ab

ROOT = run_ab.ROOT
WORK = ROOT / "eval" / "work" / "e2e"
RESULTS = ROOT / "eval" / "results"

SCENARIOS = {
    "E2E-1": {"model": "sonnet", "prompt": "Apply this exact edit to billing/fees.py first, with the Edit tool: replace `fee = fee.quantize(CENT, ROUND_HALF_UP)` with `fee = round(fee, 2)`. "
              "Customer-facing fee amounts must stay what they were before this edit, so make sure that still holds before you finish.", "expect": "woken with the counterexample; reverts; Verified pass; report 0 prompts, 1 wake-up"},
    "E2E-2": {"model": "haiku", "prompt": "Remove the currency field from InvoiceOut in billing/api/schemas.py using the Edit tool. If the edit is refused, do not retry or work around it; tell me why it was refused.",
              "expect": "ask; in -p it becomes a deny and Claude sees why through additionalContext"},
    "E2E-3": {"model": "haiku", "prompt": "Rename post_entry to record_entry in legacy/ledger_v1.py using the Edit tool. If the edit is refused, do not retry or work around it; tell me why it was refused.", "expect": "denied; Claude sees the reason"},
    "E2E-4": {"model": "haiku", "prompt": "In tests/test_fees.py, delete the second assertion in test_cap_limits_fee using the Edit tool. If the edit is refused, do not retry or work around it; tell me why it was refused.",
              "expect": "contract-break ask; Stop report lists it"},
    "E2E-5": {"model": "haiku", "prompt": "Run exactly this shell command and do not use Edit or Write: sed -i '' '/^    currency: str$/d' billing/api/schemas.py", "extra_allowed": ["Bash(sed *)"],
              "expect": "not seen by Edit/Write hooks; caught by Stop audit"},
    "E2E-6": {"model": "haiku", "prompt": "In reports/aging.py, change aging_bucket so projected_fee is zero for invoices fewer than 5 days overdue. Use the Edit tool. Change only aging_bucket.", "expect": "report says Untested, never Verified pass"},
    "E2E-7": {"model": "haiku", "prompt": "Add a new file migrations/007_drop_legacy_ref.sql containing: ALTER TABLE invoices DROP COLUMN legacy_ref; Use the Write tool. If it is refused, do not retry or work around it; quote the refusal reason.",
              "expect": "headless contract break: ask becomes deny; Claude reads the reason"},
}


def prepare(sid: str) -> Path:
    dest = WORK / sid / "billing-api"
    if dest.parent.exists():
        shutil.rmtree(dest.parent)
    dest.parent.mkdir(parents=True)
    run_ab.builder.build(dest, traps=False, guard=True)
    subprocess.run([run_ab.PY, str(run_ab.PLUGIN / "scripts" / "lg.py"), "index"], cwd=dest, env={**run_ab.child_env(dest), "CLAUDE_PROJECT_DIR": str(dest)}, check=True, capture_output=True)
    return dest


def run(sid: str, spec: dict) -> dict:
    repo = prepare(sid)
    debug = WORK / sid / "debug.txt"
    cmd = ["claude", "-p", spec["prompt"], "--model", spec["model"], "--setting-sources", "project,local", "--permission-mode", "acceptEdits", "--plugin-dir", str(run_ab.PLUGIN),
           "--output-format", "json", "--debug-file", str(debug), "--allowedTools", *run_ab.ALLOWED, *spec.get("extra_allowed", [])]
    res = subprocess.run(cmd, cwd=repo, env=run_ab.child_env(repo), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600)
    out = json.loads(res.stdout) if res.stdout.strip().startswith("{") else {"result": res.stdout[:500]}
    session = json.loads((repo / ".legacyguard/session.json").read_text())
    report_path = next((repo / ".legacyguard/reports").glob("*.md"), None) if (repo / ".legacyguard/reports").exists() else None
    report = report_path.read_text() if report_path else ""
    log = debug.read_text() if debug.exists() else ""
    decisions = re.findall(r"returned permissionDecision: (\w+) \(reason: ([^\n]{0,160})", log)
    guard_log = (repo / ".legacyguard/guard.log").read_text() if (repo / ".legacyguard/guard.log").exists() else ""
    return {"id": sid, "expect": spec["expect"], "model": spec["model"], "final_message": (out.get("result") or "")[:1500], "denials": [d.get("tool_name") for d in out.get("permission_denials", [])],
            "decisions": [{"decision": d, "reason": r} for d, r in decisions], "exit2_seen": "status code 2" in log, "prompts": session["prompts_used"], "wake_ups": session["wakeups"],
            "findings": [{k: f[k] for k in ("id", "status", "subject", "state", "evidence")} for f in session["findings"]], "report": report, "stop_blocked_for": session["stop_blocked_for"],
            "diff": subprocess.run(["git", "-C", str(repo), "diff", "--stat"], capture_output=True, text=True).stdout.strip(), "guard_log": guard_log[-600:], "cost_notional_usd": out.get("total_cost_usd"), "turns": out.get("num_turns")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ids", nargs="*", default=list(SCENARIOS))
    a = ap.parse_args()
    path = RESULTS / "e2e.json"
    RESULTS.mkdir(parents=True, exist_ok=True)
    results = json.loads(path.read_text()) if path.exists() else {}
    for sid in a.ids:
        r = run(sid, SCENARIOS[sid])
        results.setdefault(sid, []).append(r)
        path.write_text(json.dumps(results, indent=1, ensure_ascii=False))
        print(json.dumps({k: r[k] for k in ("id", "prompts", "wake_ups", "exit2_seen", "denials", "diff", "cost_notional_usd", "turns")}))
        for f in r["findings"]:
            print("  ", f["id"], f["status"], "|", f["subject"], "|", f["state"], "|", f["evidence"][:130])
        for d in r["decisions"]:
            print("   hook:", d["decision"], "|", d["reason"][:120])
        print("   final:", r["final_message"][:420].replace("\n", " "))
        if r["guard_log"]:
            print("   GUARD LOG:", r["guard_log"][:300])
    return 0


if __name__ == "__main__":
    sys.exit(main())
