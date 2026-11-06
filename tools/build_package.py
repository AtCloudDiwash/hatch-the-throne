#!/usr/bin/env python3
"""Build dist/legacyguard.zip: the plugin, its marketplace file, install.sh and a README (FR-34).

The zip holds one folder, legacyguard-package/. Nothing in it is generated: it is the files in this repo.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOP = "legacyguard-package"
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".hypothesis"}
SKIP_NAMES = {".DS_Store"}


def members() -> list[tuple[Path, str]]:
    out = [(ROOT / ".claude-plugin" / "marketplace.json", ".claude-plugin/marketplace.json"),
           (ROOT / "packaging" / "install.sh", "install.sh"), (ROOT / "packaging" / "README.txt", "README.txt")]
    for path in sorted((ROOT / "legacyguard").rglob("*")):
        rel = path.relative_to(ROOT)
        if path.is_file() and not (SKIP_PARTS & set(rel.parts)) and path.name not in SKIP_NAMES and path.suffix != ".pyc":
            out.append((path, rel.as_posix()))
    return out


def build(dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, name in members():
            info = zipfile.ZipInfo.from_file(path, f"{TOP}/{name}")
            info.compress_type = zipfile.ZIP_DEFLATED
            if name == "install.sh":
                info.external_attr = 0o100755 << 16
            zf.writestr(info, path.read_bytes())
    return dest


if __name__ == "__main__":
    target = build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "legacyguard.zip")
    print(f"{target} ({target.stat().st_size // 1024} KB, {len(members())} files)")
