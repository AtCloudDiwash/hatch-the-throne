"""Session report (FR-19): one line per finding, exactly one status each, readable in ten seconds."""
from __future__ import annotations

import re
from pathlib import Path

from guardlib import ledger

ORDER = {ledger.FAILURE: 0, ledger.DIFFERENCE: 1, ledger.UNTESTED: 2, ledger.RISK: 3, ledger.VERIFIED: 4}
HIDDEN_STATES = {"superseded"}
STATE_NOTE = {"open": "open", "applied": "edit went through", "resolved": "turned back: re-run matches baseline", "waived": "waived by developer",
              "not_applied": "edit did not land", "blocked": "denied", "recorded": ""}
FOOTER = ("Limits: the behavioral diff compares return values and exception type and message, not side effects such as database or file writes (D-029). "
          "Edits made through shell commands are only seen at this audit. Untested items were not checked. "
          "This report states what was checked; it makes no claim about what was not.")


def visible(data: dict) -> list[dict]:
    items = [f for f in data["findings"] if f["state"] not in HIDDEN_STATES]
    return sorted(items, key=lambda f: (ORDER.get(f["status"], 9), int(f["id"].split("-")[1])))


def counts(data: dict) -> dict:
    c = {s: 0 for s in ledger.STATUSES}
    for f in visible(data):
        c[f["status"]] += 1
    return c


def pinnable(data: dict) -> list[dict]:
    return [f for f in visible(data) if f["kind"] == "behavior_difference" and f.get("counterexamples")]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).replace("|", "\\|")


def _line(f: dict) -> str:
    note = STATE_NOTE.get(f["state"], f["state"])
    if f.get("last_decision") == "over_budget":
        note = "not asked: prompt budget used up"
    return f"| {f['id']} | {f['status']} | {_clean(f['subject'])} | {_clean(f['evidence'])[:220]} | {note} |"


def render(data: dict, cfg) -> str:
    c = counts(data)
    lines = [f"# LegacyGuard session report", "",
             f"Session `{data.get('session_id')}`. Mode **{cfg.mode}**. Baseline `{(data.get('baseline_commit') or 'none')[:10]}`.",
             f"Prompts used **{data['prompts_used']} of {cfg.budget}**. Claude wake-ups **{data['wakeups']}**. Edits seen {data.get('edits', 0)}.", ""]
    items = visible(data)
    if items:
        lines += ["| ID | Status | Subject | Evidence | Outcome |", "| --- | --- | --- | --- | --- |"]
        lines += [_line(f) for f in items]
    else:
        lines.append("No changes to guarded code were found this session.")
    pins = pinnable(data)
    if pins:
        lines += ["", "Pin a counterexample as a regression test:"]
        lines += [f"- `/legacyguard:pin {f['id']}` ({_clean(f['subject'])})" for f in pins]
    lines += ["", FOOTER, ""]
    return "\n".join(lines)


def summary(data: dict, cfg, path: Path | None = None) -> str:
    c = counts(data)
    turned_back = sum(1 for f in visible(data) if f["state"] == "resolved")
    open_diff = sum(1 for f in visible(data) if f["status"] == ledger.DIFFERENCE and f["state"] == "open")
    parts = [f"{c[ledger.VERIFIED]} verified pass", f"{c[ledger.FAILURE]} confirmed failure", f"{open_diff} open behavior difference", f"{turned_back} turned back",
             f"{c[ledger.UNTESTED]} untested", f"{c[ledger.RISK]} potential risk"]
    text = "LegacyGuard: " + ", ".join(parts) + f". Prompts {data['prompts_used']} of {cfg.budget}, wake-ups {data['wakeups']}."
    return text + (f" Report: {path}" if path else "")


def write(data: dict, cfg) -> Path:
    folder = cfg.state_dir / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9_-]", "_", str(data.get("session_id") or "session"))
    path = folder / f"{name}.md"
    path.write_text(render(data, cfg))
    return path
