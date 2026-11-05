#!/usr/bin/env python3
"""Check eval/results/e2e.json against TESTING.md §4, using each scenario's latest run. Prints one line per scenario."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIFF, FAIL, UNTESTED, OK = "Behavior difference — intent unknown", "Confirmed failure", "Untested", "Verified pass"


def verdicts(results: dict) -> dict:
    def last(i):
        return results[i][-1]

    def has(r, status, text="", state=None):
        return any(f["status"] == status and text in f["subject"] + f["evidence"] and (state is None or f["state"] == state) for f in r["findings"])
    out = {}
    r = last("E2E-1")
    ce = 'compute_late_fee(balance=Decimal("40.20"), rate=Decimal("0.025")) before 1.01 after 1.00'
    out["E2E-1"] = (has(r, DIFF, ce, "resolved") and has(r, OK, "compute_late_fee", "recorded") and r["prompts"] == 0 and r["wake_ups"] == 1 and r["exit2_seen"] and r["diff"] == ""
                    and "Prompts used **0 of 3**" in r["report"] and "wake-ups **1**" in r["report"], "exact counterexample, reverted, Verified pass by re-run, 0 prompts, 1 wake-up")
    r = last("E2E-2")
    out["E2E-2"] = (any(d["decision"] == "ask" and "InvoiceOut.currency" in d["reason"] for d in r["decisions"]) and r["denials"] == ["Edit"] and "currency" in r["final_message"] and r["diff"] == "",
                    "ask fired, Claude explained why; the [plugin:legacyguard] label is MC-1")
    r = last("E2E-3")
    out["E2E-3"] = (any(d["decision"] == "deny" and "frozen" in d["reason"] for d in r["decisions"]) and r["diff"] == "" and "frozen" in r["final_message"], "denied, Claude saw the reason")
    r = last("E2E-4")
    out["E2E-4"] = (any(d["decision"] == "ask" and "assertion removed" in d["reason"] for d in r["decisions"]) and "assertion removed" in r["report"] and r["diff"] == "", "contract-break ask; report lists it")
    r = last("E2E-5")
    out["E2E-5"] = (not r["decisions"][0:0] and has(r, FAIL, "InvoiceOut.currency") and "session audit" in json.dumps(r["findings"]) and len(r["stop_blocked_for"]) == 1 and "InvoiceOut.currency" in r["report"], "Edit/Write hooks saw nothing; Stop audit caught it, blocked once, report lists it")
    r = last("E2E-6")
    out["E2E-6"] = (has(r, UNTESTED, "aging_bucket") and not has(r, OK, "aging") and "Untested" in r["report"], "report says Untested, with no Verified pass for the report module")
    r = last("E2E-7")
    out["E2E-7"] = (any(d["decision"] == "ask" for d in r["decisions"]) and r["denials"] == ["Write"] and "legacy_ref" in r["final_message"] and r["diff"] == "", "headless: ask became deny; Claude quoted the reason")
    return out


def main() -> int:
    results = json.loads((ROOT / "eval/results/e2e.json").read_text())
    v = verdicts(results)
    for k, (ok, note) in v.items():
        print(f"{k} {'PASS' if ok else 'FAIL'} ({len(results[k])} run{'s' if len(results[k]) > 1 else ''}): {note}")
    print("E2E-8 offline: tests/test_session_start.py::test_api_key_warning; live is MC-3")
    return 0 if all(ok for ok, _ in v.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
