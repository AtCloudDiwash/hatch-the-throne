"""Shared hook runtime: stdin JSON, fail-open wrapper, one JSON object on stdout (T1.2)."""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import traceback
from pathlib import Path

PLUGIN_ROOT = str(Path(__file__).resolve().parent.parent)
if PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)

CONTEXT_LIMIT = 1500


class Wake(Exception):
    """Exit 2 with this text on stderr: wakes Claude. Only the behavioral diff raises it (D-004)."""


def clip(text: str, limit: int = CONTEXT_LIMIT) -> str:
    if len(text) <= limit:
        return text
    suffix = f" … (+{len(text) - limit + 20} chars cut)"
    return text[: limit - len(suffix)] + suffix


def clip_output(out: dict) -> dict:
    hso = out.get("hookSpecificOutput")
    if isinstance(hso, dict) and isinstance(hso.get("additionalContext"), str):
        hso["additionalContext"] = clip(hso["additionalContext"])
    return out


def log_error(cwd: str | None, message: str) -> None:
    """Append to .legacyguard/guard.log if that folder exists, else to the plugin's data folder."""
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    candidates = []
    if cwd:
        try:
            from guardlib.paths import find_root
            candidates.append(Path(find_root(cwd)) / ".legacyguard")
        except Exception:  # noqa: BLE001 - logging must never raise
            pass
    if os.environ.get("CLAUDE_PLUGIN_DATA"):
        candidates.append(Path(os.environ["CLAUDE_PLUGIN_DATA"]))
    for folder in candidates:
        if folder.is_dir():
            try:
                with open(folder / "guard.log", "a") as fh:
                    fh.write(f"{stamp} {message}\n")
                return
            except OSError:
                continue


def run_hook(handler) -> None:
    """Run handler(event) -> dict | None. Any internal error: log, exit 0, print nothing."""
    real_stdout, sys.stdout = sys.stdout, sys.stderr  # stray prints must not corrupt the JSON channel
    cwd = None
    try:
        event = json.load(sys.stdin)
        cwd = event.get("cwd")
        out = handler(event)
        if out:
            real_stdout.write(json.dumps(clip_output(out)))
            real_stdout.flush()
    except Wake as wake:
        sys.stderr.write(clip(str(wake)))
        sys.stderr.flush()
        os._exit(2)
    except BaseException:  # noqa: BLE001 - fail open on everything, including SystemExit from libraries
        log_error(cwd, f"{Path(sys.argv[0]).name}: {traceback.format_exc()}")
    sys.stderr.flush()
    os._exit(0)


def hook_output(event_name: str, *, context: str | None = None, decision: str | None = None,
                reason: str | None = None, system_message: str | None = None) -> dict | None:
    """Build one output object. An allow is expressed by omitting permissionDecision (see DL log)."""
    hso: dict = {}
    if decision:
        hso["permissionDecision"] = decision
    if reason:
        hso["permissionDecisionReason"] = reason
    if context:
        hso["additionalContext"] = context
    out: dict = {}
    if hso:
        hso["hookEventName"] = event_name
        out["hookSpecificOutput"] = hso
    if system_message:
        out["systemMessage"] = system_message
    return out or None


def ensure_deps() -> None:
    """Re-exec under the guard's venv if needed. Raises BootstrapError if it is not installed."""
    from guardlib import bootstrap
    bootstrap.reexec_in_venv(PLUGIN_ROOT)


def load_guard(event: dict):
    """(root, Config), or (root, None) when the guard is inactive for this repo. Fails open."""
    from guardlib import config as cfgmod
    from guardlib.paths import find_root
    root = find_root(event.get("cwd") or os.getcwd())
    try:
        return root, cfgmod.load_config(root)
    except (cfgmod.ConfigMissing, cfgmod.ConfigError):
        return root, None
