#!/usr/bin/env python3
"""Clone django-oscar and install it for the backtest (FR-28). Output goes to eval/work/, which git ignores."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
REPO = WORK / "oscar"
VENV = WORK / "oscar-venv"
COMMIT = "a5ed3c9"
PY312 = "/opt/homebrew/bin/python3.12"

CONFIG = """scope: ./
language: python
mode: guarded
python: {python}
django_settings: tests.settings
source_roots: [src, .]
contracts:
  db: src/oscar/apps/offer/migrations/
behavioral_diff:
  network: blocked
  max_inputs: 80
  timeout_s: 60
  self_diff: true
  env:
    DATABASE_ENGINE: django.db.backends.sqlite3
    DATABASE_NAME: ":memory:"
"""


def main() -> None:
    WORK.mkdir(exist_ok=True)
    if not REPO.exists():
        subprocess.run(["git", "clone", "-q", "--depth", "300", "https://github.com/django-oscar/django-oscar.git", str(REPO)], check=True)
    subprocess.run(["git", "-C", str(REPO), "checkout", "-q", "--detach", COMMIT], check=True)
    if not VENV.exists():
        py = PY312 if Path(PY312).exists() else sys.executable
        subprocess.run([py, "-m", "venv", str(VENV)], check=True)
        subprocess.run([str(VENV / "bin/pip"), "-q", "install", "-e", f"{REPO}[test]"], check=True)
    (REPO / ".legacyguard").mkdir(exist_ok=True)
    (REPO / ".legacyguard/config.yaml").write_text(CONFIG.format(python=VENV / "bin/python"))
    print("ready:", REPO)


if __name__ == "__main__":
    main()
