"""T13.2: the download package holds the plugin, its marketplace file and a runnable installer (FR-34)."""
import json
import subprocess
import zipfile

import build_package


def test_zip_has_what_the_installer_needs(tmp_path):
    z = zipfile.ZipFile(build_package.build(tmp_path / "lg.zip"))
    names = set(z.namelist())
    top = build_package.TOP
    for needed in ("install.sh", "README.txt", ".claude-plugin/marketplace.json", "legacyguard/.claude-plugin/plugin.json",
                   "legacyguard/hooks/hooks.json", "legacyguard/requirements.txt", "legacyguard/guardlib/autosetup.py"):
        assert f"{top}/{needed}" in names
    assert not [n for n in names if "__pycache__" in n or n.endswith(".pyc")]
    assert (z.getinfo(f"{top}/install.sh").external_attr >> 16) & 0o111
    market = json.loads(z.read(f"{top}/.claude-plugin/marketplace.json"))
    assert market["name"] == "legacyguard" and market["plugins"][0]["source"] == "./legacyguard"


def test_installer_stops_with_a_plain_message_when_claude_is_missing(tmp_path):
    zipfile.ZipFile(build_package.build(tmp_path / "lg.zip")).extractall(tmp_path)
    r = subprocess.run(["/bin/sh", str(tmp_path / build_package.TOP / "install.sh")], capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "LEGACYGUARD_HOME": str(tmp_path / "h")})
    assert r.returncode == 1 and "Claude Code was not found" in r.stdout and not (tmp_path / "h").exists()
