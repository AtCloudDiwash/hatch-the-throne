#!/usr/bin/env python3
"""Fail if the dev log and git history disagree. Stdlib only."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REQUIRED = ["id", "time", "milestone", "task", "type", "title", "context", "what", "why", "root_cause",
            "impact", "files", "refs", "links", "commit", "evidence"]
TYPES = {"feature", "change", "fix", "decision", "fallback", "blocked", "spike"}
DL = re.compile(r"DL-\d{3,}")


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def check(repo: Path, log: Path) -> list[str]:
    problems: list[str] = []
    entries = [json.loads(l) for l in log.read_text().splitlines() if l.strip()]
    ids = [e.get("id") for e in entries]
    known = set(ids)
    if len(known) != len(ids):
        problems.append("duplicate DL IDs in the log")
    for e in entries:
        eid = e.get("id", "?")
        for k in REQUIRED:
            if k not in e:
                problems.append(f"{eid}: missing key {k}")
        if e.get("type") not in TYPES:
            problems.append(f"{eid}: unknown type {e.get('type')!r}")
        if e.get("type") == "fix" and not str(e.get("root_cause", "")).strip():
            problems.append(f"{eid}: fix entry has an empty root_cause")
        for kind, targets in e.get("links", {}).items():
            for t in targets:
                if t not in known:
                    problems.append(f"{eid}: links.{kind} references unknown {t}")
    rel = log.resolve().relative_to(repo.resolve()).as_posix()
    added = git(repo, "log", "--diff-filter=A", "--format=%H", "--", rel).split()
    if added:
        lines = git(repo, "log", "-1", "--format=%h\t%s", added[-1]).splitlines()
        lines += git(repo, "log", "--format=%h\t%s", f"{added[-1]}..HEAD").splitlines()
        for line in lines:
            sha, _, subject = line.partition("\t")
            found = DL.findall(subject)
            if not found:
                problems.append(f"commit {sha} has no DL ID: {subject}")
            for f in found:
                if f not in known:
                    problems.append(f"commit {sha} references unknown {f}")
    return problems


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, default=root)
    ap.add_argument("--log", type=Path, default=root / "docs" / "devlog.jsonl")
    a = ap.parse_args()
    problems = check(a.repo, a.log)
    for p in problems:
        print("FAIL", p)
    if problems:
        return 1
    n = sum(1 for l in a.log.read_text().splitlines() if l.strip())
    print(f"devlog_check OK: {n} entries, every commit carries a known DL ID, links resolve, fixes have root causes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
