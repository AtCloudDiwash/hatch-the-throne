#!/usr/bin/env python3
"""T7.4: compare measured rates with the D-013 targets. Reports misses; changes nothing."""
import json
from pathlib import Path

R = Path(__file__).resolve().parent / "results"
replay = json.loads((R / "backtest/replay.json").read_text())["summary"]
planted = json.loads((R / "backtest/planted.json").read_text())
ab = json.loads((R / "ab.json").read_text())
rows = [("Developer prompts per 10 edits", replay["prompt_rate_per_10_edits"], "at most 1", replay["prompt_rate_per_10_edits"] <= 1),
        ("Harmless wake-ups per 20 edits", replay["wake_up_rate_per_20_edits"], "at most 1", replay["wake_up_rate_per_20_edits"] <= 1),
        ("Wrong blocks (denies on real commits)", replay["denies"], "0", replay["denies"] == 0)]
for name, value, target, ok in rows:
    print(f"{name}: {value} (target {target}): {'met' if ok else 'MISSED'}")
print(f"Prompts per session: most in any A/B session was {max(r['prompts'] for r in ab['runs'])} (cap 3, enforced by test)")
print(f"Catch rate, any status except Verified pass: {planted['catch_rate_any_non_pass']:.0%}; proved by execution: {planted['catch_rate_proved_by_execution']:.0%} (no target, D-033)")
print(f"Functions: {replay['function_statuses']}")
print(json.dumps(ab["summary"]))
