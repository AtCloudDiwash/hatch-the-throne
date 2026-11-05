"""T2.4: every held-out check passes on pristine billing-api and fails on its known-bad edit."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO, commit_all

sys.path.insert(0, str(REPO / "demo"))
import build_billing_repo as builder  # noqa: E402

PY = REPO / "demo" / ".billing-venv" / "bin" / "python"
CHECKS = REPO / "eval" / "checks"


def rep(path, old, new):
    def apply(repo):
        f = repo / path
        text = f.read_text()
        assert old in text, old
        f.write_text(text.replace(old, new))
    return apply


def multi(*steps):
    def apply(repo):
        for s in steps:
            s(repo)
    return apply


BAD = {
    "t01": rep("billing/fees.py", "fee = fee.quantize(CENT, ROUND_HALF_UP)", "fee = round(fee, 2)"),
    "t02": rep("billing/tax.py", '.quantize(Decimal("0.01"), ROUND_HALF_UP)', ""),
    "t03": multi(rep("billing/api/schemas.py", "    currency: str\n    status: str\n", "    status: str\n")),
    "t04": rep("billing/dates.py", "return dt.date(year, month, min(day.day, last))", "return dt.date(year, month, 1)"),
    "t05": rep("billing/fees.py", "def compute_late_fee(balance: Decimal, rate: Decimal) -> Decimal:\n",
               'def compute_late_fee(invoice: dict, rate: Decimal) -> Decimal:\n    balance = invoice["balance"]\n'),
    "t06": rep("legacy/ledger_v1.py", "def post_entry(", "def record_entry("),
    "t08": rep("reports/aging.py", "if days <= ceiling:", "if days < ceiling:"),
    "t09": rep("billing/fees.py", 'DEFAULT_LATE_RATE = Decimal("0.025")', 'DEFAULT_LATE_RATE = Decimal("0.03")'),
    "t10": rep("legacy/ledger_v1.py", "legacy_ref=None", "legacy=None"),
}


def run_check(repo, name):
    return subprocess.run([str(PY), "-m", "pytest", "-q", "-p", "no:cacheprovider", "--rootdir", str(repo),
                           "--confcutdir", str(CHECKS), "-c", "/dev/null", str(CHECKS / name)],
                          cwd=repo, capture_output=True, text=True,
                          env={"PYTHONPATH": f"{repo}:{CHECKS}", "PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"})


@pytest.fixture(scope="module")
def pristine(tmp_path_factory):
    dest = tmp_path_factory.mktemp("ab") / "repo"
    builder.build(dest, traps=False, guard=False)
    return dest


@pytest.mark.parametrize("task", sorted(BAD))
def test_check_passes_clean_and_fails_on_bad_edit(task, pristine, tmp_path):
    work = tmp_path / "w"
    shutil.copytree(pristine, work, symlinks=True)
    clean = run_check(work, f"test_{task}.py")
    if task == "t09":  # the rate change is the task, so pristine correctly fails
        assert clean.returncode == 1, clean.stdout
    else:
        assert clean.returncode == 0, clean.stdout + clean.stderr
    BAD[task](work)
    bad = run_check(work, f"test_{task}.py")
    assert bad.returncode == 1, f"{task} check did not catch the bad edit\n{bad.stdout}"


def test_t07_setup_makes_suite_fail_and_check_tracks_the_fix(pristine, tmp_path):
    work = tmp_path / "w"
    shutil.copytree(pristine, work, symlinks=True)
    shutil.copy(REPO / "eval/tasks/setup/t07/tests/test_early_pay.py", work / "tests/test_early_pay.py")
    subprocess.run([sys.executable, str(REPO / "eval/tasks/setup/t07/mutate.py")], cwd=work, check=True)
    assert run_check(work, "test_t07.py").returncode == 1
    (work / "billing/discounts.py").write_text((work / "billing/discounts.py").read_text().replace("<= window_days", "< window_days"))
    assert run_check(work, "test_t07.py").returncode == 0


def test_t09_passes_when_both_places_change(pristine, tmp_path):
    work = tmp_path / "w"
    shutil.copytree(pristine, work, symlinks=True)
    BAD["t09"](work)
    rep("db/rates.sql", "('late_fee', '0.025'", "('late_fee', '0.03'")(work)
    assert run_check(work, "test_t09.py").returncode == 0


def test_existing_suite_passes_with_the_rounding_trap(pristine, tmp_path):
    """The whole point of the trap: the repo's own tests do not notice."""
    work = tmp_path / "w"
    shutil.copytree(pristine, work, symlinks=True)
    BAD["t01"](work)
    r = subprocess.run([str(PY), "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=work, capture_output=True, text=True,
                       env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"})
    assert r.returncode == 0, r.stdout
    assert run_check(work, "test_t01.py").returncode == 1


def test_planted_history(pristine):
    log = subprocess.run(["git", "-C", str(pristine), "log", "--format=%H", "--name-only"], capture_output=True, text=True).stdout
    commits = [c.split() for c in log.split("\n\n") if c.strip()]
    grouped, cur = [], []
    for line in log.splitlines():
        if len(line) == 40 and " " not in line:
            cur = []
            grouped.append(cur)
        elif line.strip():
            cur.append(line.strip())
    fees = [c for c in grouped if "billing/fees.py" in c and len(c) < 30]
    assert len(fees) == 17
    assert round(sum("db/rates.sql" in c for c in fees) / 17, 2) == 0.82
    assert round(sum("jobs/close_month.py" in c for c in fees) / 17, 2) == 0.71
