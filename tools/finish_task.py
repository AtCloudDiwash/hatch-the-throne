#!/usr/bin/env python3
"""Close out one task: log entries, update PROGRESS.md, regenerate the map, commit, backfill the hash.

Reads a JSON list of dev log entries on stdin; id, time, milestone, task and commit are filled in and
omitted keys default to empty. The evidence command must exit 0 for status "done".
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import devlog_viz  # noqa: E402
import progress as prog  # noqa: E402

LOG = ROOT / "docs" / "devlog.jsonl"


def now() -> str:
    s = dt.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M%z")
    return s[:-2] + ":" + s[-2:]


def next_num() -> int:
    if not LOG.exists():
        return 1
    return 1 + sum(1 for l in LOG.read_text().splitlines() if l.strip())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("task")
    ap.add_argument("--status", default="done", choices=["done", "blocked", "skipped", "in_progress"])
    ap.add_argument("--evidence-cmd", default="")
    ap.add_argument("--evidence-text", default="")
    ap.add_argument("--msg", required=True)
    ap.add_argument("--current", default="", help="task now in progress")
    ap.add_argument("--next", default="", dest="next_step", help="next step in plain words")
    ap.add_argument("--tail", type=int, default=20)
    ap.add_argument("--final", action="store_true", help="last commit: a commit cannot contain its own hash, so leave the tree clean")
    a = ap.parse_args()

    evidence = a.evidence_text
    if a.evidence_cmd:
        run = subprocess.run(a.evidence_cmd, shell=True, cwd=ROOT, capture_output=True, text=True)
        tail = "\n".join((run.stdout + run.stderr).strip().splitlines()[-a.tail:])
        evidence = f"$ {a.evidence_cmd}\n{tail}\n(exit {run.returncode})" + (f"\n{a.evidence_text}" if a.evidence_text else "")
        if run.returncode and a.status in ("done", "in_progress"):
            print(evidence)
            print("evidence command failed; nothing committed", file=sys.stderr)
            return 1

    state = prog.load()
    task = state["tasks"][a.task]
    raw = json.load(sys.stdin)
    entries = []
    n = next_num()
    for i, item in enumerate(raw):
        refs = {"requirements": [], "decisions": [], "open_questions": [], "tests": [], **item.get("refs", {})}
        links = {"caused_by": [], "supersedes": [], "related": [], **item.get("links", {})}
        e = {"id": f"DL-{n + i:03d}", "time": now(), "milestone": task["milestone"], "task": a.task,
             "type": item["type"], "title": item["title"], "context": item.get("context", ""),
             "what": item.get("what", ""), "why": item.get("why", ""), "root_cause": item.get("root_cause", ""),
             "impact": item.get("impact", ""), "files": item.get("files", []), "refs": refs, "links": links,
             "commit": "this commit is the last one; see git log -1" if a.final else "", "evidence": item.get("evidence") or evidence}
        entries.append(e)
    with LOG.open("a") as fh:
        for e in entries:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    ids = [e["id"] for e in entries]

    task["status"] = a.status
    task["evidence"] = evidence
    task["dl"] = task.get("dl", []) + ids
    if a.current:
        state["current"] = a.current
    if a.next_step:
        state["next"] = a.next_step
    prog.save(state)
    docs = ROOT / "docs"
    devlog_viz.generate(LOG, docs / "REQUIREMENTS.md", docs / "PROGRESS.md", docs / "DEVLOG.md", docs / "devlog.html")

    subject = f"{a.task} {' '.join(ids)} {a.msg}"
    body = "\n".join(f"{e['id']} {e['type']}: {e['title']}" for e in entries)
    message = f"{subject}\n\n{body}\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\n"
    subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
    subprocess.run(["git", "commit", "-q", "-F", "-"], cwd=ROOT, input=message, text=True, check=True)
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()

    if a.final:
        print(f"{subject}  [{sha}]")
        return 0
    lines = LOG.read_text().splitlines()
    out = []
    for line in lines:
        e = json.loads(line)
        if e["id"] in ids:
            e["commit"] = sha
            line = json.dumps(e, ensure_ascii=False)
        out.append(line)
    LOG.write_text("\n".join(out) + "\n")
    state = prog.load()
    state["tasks"][a.task]["commit"] = sha
    prog.save(state)
    print(f"{subject}  [{sha}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
