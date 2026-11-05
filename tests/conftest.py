import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "legacyguard"
for p in (PLUGIN, PLUGIN / "scripts", REPO / "tools"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def run_script(name, event, env=None):
    full_env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    full_env.update(env or {})
    return subprocess.run([sys.executable, str(PLUGIN / "scripts" / f"{name}.py")], input=json.dumps(event),
                          capture_output=True, text=True, env=full_env, timeout=120)


@pytest.fixture
def hook():
    return run_script


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          capture_output=True, text=True, check=True).stdout


def commit_all(repo, msg="c"):
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", msg)


@pytest.fixture
def repo(tmp_path):
    """A small guarded git repo with a config file and one commit."""
    root = tmp_path / "svc"
    (root / ".legacyguard").mkdir(parents=True)
    (root / ".legacyguard" / "config.yaml").write_text("scope: .\nmode: guarded\nfrozen:\n  - legacy/ledger.py\n")
    (root / "app.py").write_text("def add(a, b):\n    return a + b\n")
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    commit_all(root, "init")
    return root
