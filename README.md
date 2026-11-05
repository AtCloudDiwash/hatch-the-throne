# LegacyGuard

A Claude Code plugin that guards one Python backend: contract checks before writes, old-versus-new behavioral diffs after them, and a session audit at Stop. It makes no model calls and needs no API key.

Start with [docs/FINAL_REPORT.md](docs/FINAL_REPORT.md). The plugin is in [legacyguard/](legacyguard/README.md).

```bash
python3 demo/build_billing_repo.py
cd demo/billing-api
../../.venv/bin/python ../../legacyguard/scripts/lg.py index
claude --plugin-dir ../../legacyguard
```

`.venv` is the guard's development environment. To create it from the repo root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r legacyguard/requirements.txt pytest pytest-timeout
.venv/bin/pytest -q tests
```

To read why every change happened, open `docs/devlog.html` in a browser, or view `docs/DEVLOG.md` on GitHub.
