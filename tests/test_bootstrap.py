"""T1.3: the guard's venv installs once and reports failure with the manual command."""
import subprocess
import types

import pytest

from conftest import PLUGIN
from guardlib import bootstrap


def fake_run(calls, code=0):
    def run(cmd, **kw):
        calls.append(cmd)
        if cmd[1:3] == ["-m", "venv"]:
            (bootstrap.venv_python(fake_run.base)).parent.mkdir(parents=True, exist_ok=True)
            bootstrap.venv_python(fake_run.base).write_text("")
        return types.SimpleNamespace(returncode=code, stdout="", stderr="no network")
    return run


def test_second_start_skips_install(tmp_path):
    calls = []
    fake_run.base = tmp_path
    assert bootstrap.ensure_venv(PLUGIN, tmp_path, run=fake_run(calls)) is True
    n = len(calls)
    assert n == 2
    assert bootstrap.ensure_venv(PLUGIN, tmp_path, run=fake_run(calls)) is False
    assert len(calls) == n


def test_failure_raises_and_leaves_no_marker(tmp_path):
    fake_run.base = tmp_path
    with pytest.raises(bootstrap.BootstrapError, match="no network"):
        bootstrap.ensure_venv(PLUGIN, tmp_path, run=fake_run([], code=1))
    assert not bootstrap.is_ready(PLUGIN, tmp_path)
    assert "pip install -r" in bootstrap.manual_command(PLUGIN, tmp_path)


def test_reexec_switches_into_venv_even_though_python_is_a_symlink(tmp_path, repo):
    """Regression: comparing resolved interpreter paths treated the venv as already active."""
    import json
    import os
    import subprocess
    import sys
    data = tmp_path / "data"
    subprocess.run([sys.executable, "-m", "venv", str(data / "venv")], check=True)
    site = next((data / "venv" / "lib").glob("python*/site-packages"))
    for mod in ("yaml", "tree_sitter", "tree_sitter_python"):
        (site / mod).mkdir()
        (site / mod / "__init__.py").write_text("")
    bare = tmp_path / "bare"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(bare)], check=True)
    code = ("import sys; sys.path.insert(0, %r); from guardlib import bootstrap\n"
            "bootstrap.reexec_in_venv(%r)\nprint(sys.prefix)" % (str(PLUGIN), str(PLUGIN)))
    script = tmp_path / "probe.py"
    script.write_text(code)
    r = subprocess.run([str(bare / "bin" / "python"), str(script)], capture_output=True, text=True,
                       env={"PATH": os.environ["PATH"], "CLAUDE_PLUGIN_DATA": str(data)})
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == os.path.realpath(data / "venv") or r.stdout.strip() == str(data / "venv")


def test_old_python_with_no_newer_one_is_named_in_plain_words(tmp_path):
    """DL-089: Python 3.9 used to surface as 'No matching distribution found for mcp'."""
    calls = []
    fake_run.base = tmp_path
    with pytest.raises(bootstrap.BootstrapError, match=r"needs Python 3\.10 or newer.*3\.9\.6"):
        bootstrap.ensure_venv(PLUGIN, tmp_path, run=fake_run(calls), version=(3, 9, 6), finder=lambda: None)
    assert calls == []


def test_old_python_uses_a_newer_one_found_on_the_machine(tmp_path):
    """FR-33: the python3 command is 3.9 but a 3.12 is installed, so the guard's environment is built with that."""
    calls = []
    fake_run.base = tmp_path
    assert bootstrap.ensure_venv(PLUGIN, tmp_path, run=fake_run(calls), version=(3, 9, 6), finder=lambda: "/x/python3.12") is True
    assert calls[0][:3] == ["/x/python3.12", "-m", "venv"]


def test_find_python_returns_only_3_10_or_newer():
    found = bootstrap.find_python()
    assert found is None or bootstrap._python_version(found) >= (3, 10)
