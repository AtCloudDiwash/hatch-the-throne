"""T13.1: a Python git repo sets itself up on first use (FR-32, D-042)."""
import json
import subprocess

import yaml

from conftest import commit_all
from guardlib import autosetup, config as cfgmod


def make(root, files):
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    commit_all(root, "init")
    return root


FLAT = {"app.py": "def add(a, b):\n    return a + b\n", "util.py": "X = 1\n", "tests/test_app.py": "def test_a():\n    assert True\n"}
SRC = {"src/shop/__init__.py": "", "src/shop/money.py": "def cents(x):\n    return x * 100\n", "src/tests/__init__.py": "",
       "src/tests/settings.py": "SECRET_KEY = 'x'\n", "src/shop/settings.py": "SECRET_KEY = 'y'\n",
       "src/setup.cfg": "[tool:pytest]\nDJANGO_SETTINGS_MODULE = tests.settings\n",
       "src/manage.py": 'import os\nos.environ.setdefault("DJANGO_SETTINGS_MODULE", "shop.settings")\n'}


def start(hook, repo):
    r = hook("session_start", {"cwd": str(repo), "session_id": "s", "source": "startup"})
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout) if r.stdout else {}


def test_flat_repo_gets_a_config_and_starts_guarded(tmp_path, hook):
    repo = make(tmp_path / "svc", FLAT)
    o = start(hook, repo)
    assert "set itself up" in o["systemMessage"] and "LegacyGuard is active" in o["hookSpecificOutput"]["additionalContext"]
    cfg = cfgmod.load_config(str(repo))
    assert cfg.scope == "./" and cfg.mode == "guarded" and cfg.source_roots == []
    assert (repo / ".legacyguard" / "index.db").exists() and (repo / ".legacyguard" / "baseline").is_dir()
    assert "No .venv folder" in o["systemMessage"]
    assert subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "--", "app.py", "util.py", "tests"],
                          capture_output=True, text=True).stdout == ""


def test_second_start_says_nothing_about_setup_and_keeps_edits(tmp_path, hook):
    repo = make(tmp_path / "svc", FLAT)
    start(hook, repo)
    path = repo / ".legacyguard" / "config.yaml"
    path.write_text(path.read_text().replace("mode: guarded", "mode: advisory"))
    o = start(hook, repo)
    assert "set itself up" not in o.get("systemMessage", "") and cfgmod.load_config(str(repo)).mode == "advisory"


def test_src_layout_prefers_pytest_settings_over_manage_py(tmp_path):
    repo = make(tmp_path / "svc", SRC)
    found = autosetup.detect(repo)
    assert found["scope"] == "src/" and found["source_roots"] == ["src"] and found["django_settings"] == "tests.settings"
    data = yaml.safe_load(autosetup.render(found))
    assert data["django_settings"] == "tests.settings" and data["source_roots"] == ["src"] and data["frozen"] == []


def test_settings_module_that_does_not_exist_is_skipped(tmp_path):
    files = dict(SRC)
    del files["src/tests/settings.py"]
    assert autosetup.detect(make(tmp_path / "svc", files))["django_settings"] == "shop.settings"


def test_openapi_file_becomes_the_http_contract(tmp_path):
    repo = make(tmp_path / "svc", {**FLAT, "openapi.yaml": "openapi: 3.0.0\n"})
    assert yaml.safe_load(autosetup.render(autosetup.detect(repo)))["contracts"] == {"http": "openapi.yaml"}


def test_repo_with_almost_no_python_is_left_alone(tmp_path, hook):
    repo = make(tmp_path / "web", {"index.js": "1\n", "build.py": "print(1)\n"})
    assert start(hook, repo) == {} and not (repo / ".legacyguard").exists()


def test_enabled_false_keeps_the_guard_off_and_quiet(tmp_path, hook):
    repo = make(tmp_path / "svc", FLAT)
    (repo / ".legacyguard").mkdir()
    (repo / ".legacyguard" / "config.yaml").write_text("enabled: false\n")
    assert start(hook, repo) == {}
    assert not (repo / ".legacyguard" / "baseline").exists()
    r = hook("pre_edit", {"cwd": str(repo), "session_id": "s", "tool_name": "Edit",
                          "tool_input": {"file_path": str(repo / "app.py"), "old_string": "a + b", "new_string": "a - b"}})
    assert r.returncode == 0 and r.stdout == ""
