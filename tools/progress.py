#!/usr/bin/env python3
"""docs/progress_state.json is the data; docs/PROGRESS.md is rendered from it.

Usage: progress.py summary M3 "five lines" | progress.py current T4.1 "next step"
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
STATE = DOCS / "progress_state.json"
MD = DOCS / "PROGRESS.md"
ICON = {"done": "[x]", "blocked": "[!]", "skipped": "[-]", "in_progress": "[~]", "pending": "[ ]"}


def load() -> dict:
    return json.loads(STATE.read_text())


def render(state: dict) -> str:
    tasks = state["tasks"]
    out = ["# PROGRESS", "",
           "Rendered from `docs/progress_state.json` by `tools/progress.py`. To resume after an interruption, "
           "read this file and `docs/devlog.jsonl`, then continue from the first task not marked done.", "",
           f"- **Current milestone and task:** {state['current']}",
           f"- **Next step:** {state['next']}", "",
           "## Status", "", "| Task | Milestone | Status | Title | Dev log | Commit |", "| --- | --- | --- | --- | --- | --- |"]
    for tid, t in tasks.items():
        out.append(f"| {tid} | {t['milestone']} | {t['status']} | {ICON[t['status']]} {t['title']} | {' '.join(t.get('dl', []))} | {t.get('commit', '')} |")
    if state.get("summaries"):
        out += ["", "## Milestone summaries", ""]
        for ms, text in state["summaries"].items():
            out += [f"### {ms}", "", text, ""]
    out += ["", "## Evidence", ""]
    for tid, t in tasks.items():
        if t.get("evidence"):
            out += [f"### {tid} {t['title']} ({t['status']})", "", "```text", t["evidence"], "```", ""]
    return "\n".join(out) + "\n"


def save(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n")
    MD.write_text(render(state))


if __name__ == "__main__":
    s = load()
    if sys.argv[1] == "summary":
        s.setdefault("summaries", {})[sys.argv[2]] = sys.argv[3]
    elif sys.argv[1] == "current":
        s["current"] = sys.argv[2]
        s["next"] = sys.argv[3]
    save(s)
