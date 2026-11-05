import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import devlog_check  # noqa: E402
import devlog_viz  # noqa: E402


def entry(n, type_="feature", **kw):
    base = {"id": f"DL-{n:03d}", "time": "2026-11-05T14:02-06:00", "milestone": f"M{n % 3}", "task": f"T{n % 3}.1",
            "type": type_, "title": f"Entry {n}", "context": "c", "what": "w", "why": "y", "root_cause": "",
            "impact": "i", "files": ["a.py"],
            "refs": {"requirements": ["FR-01"], "decisions": ["D-001"], "open_questions": ["OQ-B1"], "tests": []},
            "links": {"caused_by": [], "supersedes": [], "related": []}, "commit": "abc1234", "evidence": "$ x\nok"}
    base.update(kw)
    return base


def fixture():
    return [entry(1), entry(2, "decision"),
            entry(3, "fix", root_cause="bad <script>", links={"caused_by": ["DL-001"], "supersedes": [], "related": []}),
            entry(4, "change", links={"caused_by": [], "supersedes": ["DL-002"], "related": ["DL-001"]}),
            entry(5, "blocked")]


def write(path, entries):
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))


def test_viz_outputs_every_id(tmp_path):
    log = tmp_path / "log.jsonl"
    write(log, fixture())
    req = tmp_path / "REQ.md"
    req.write_text("### FR-01 One — Confirmed — MVP\n### FR-02 Two — Confirmed — MVP\n")
    prog = tmp_path / "P.md"
    prog.write_text("| T1.1 | M1 | done | x |\n")
    md, html = tmp_path / "D.md", tmp_path / "d.html"
    devlog_viz.generate(log, req, prog, md, html)
    m, h = md.read_text(), html.read_text()
    for n in range(1, 6):
        assert f"DL-{n:03d}" in m
        assert f"DL-{n:03d}" in h
    assert "flowchart LR" in m and "-->|caused|" in m and "|replaces|" in m
    assert "subgraph M1" in m
    assert "http://" not in h and "https://" not in h, "html must work offline"
    assert "<script>\"" not in h and "bad <script>" not in h, "embedded text must be escaped"
    assert "prefers-color-scheme:dark" in h


def init_repo(tmp_path, subject):
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    log = tmp_path / "docs" / "devlog.jsonl"
    log.parent.mkdir()
    write(log, fixture())
    for args in (["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", subject]):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True)
    return log


def test_check_passes_on_good_log(tmp_path):
    log = init_repo(tmp_path, "T1.1 DL-001 good")
    assert devlog_check.check(tmp_path, log) == []


def test_check_flags_commit_without_id(tmp_path):
    log = init_repo(tmp_path, "T1.1 DL-001 good")
    (tmp_path / "x").write_text("x")
    for args in (["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "no id here"]):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True)
    assert any("has no DL ID" in p for p in devlog_check.check(tmp_path, log))


def test_check_flags_bad_link_and_empty_root_cause(tmp_path):
    log = init_repo(tmp_path, "T1.1 DL-001 good")
    bad = fixture()
    bad[0]["links"]["related"] = ["DL-999"]
    bad[2]["root_cause"] = ""
    write(log, bad)
    problems = devlog_check.check(tmp_path, log)
    assert any("DL-999" in p for p in problems)
    assert any("empty root_cause" in p for p in problems)
