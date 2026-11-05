#!/usr/bin/env python3
"""SessionStart: bootstrap, baseline, session reset, API-key warning, context summary (FR-03, FR-10)."""
import os

import _common
from _common import PLUGIN_ROOT, hook_output, log_error, run_hook

SETUP = ("LegacyGuard is installed but inactive here: no .legacyguard/config.yaml. "
         "To guard this repo, add that file (see the plugin README), then run /legacyguard:index.")
API_KEY = ("LegacyGuard: ANTHROPIC_API_KEY is set, so Claude Code bills that key per token instead of your plan. "
           "The guard never uses it. Unset it to stay on your plan.")


def summary(cfg) -> str:
    c = cfg.raw.get("contracts") or {}
    contracts = ", ".join(f"{k}={v}" for k, v in c.items()) or "none"
    frozen = ", ".join(cfg.raw.get("frozen") or []) or "none"
    return (f"LegacyGuard is active. Scope: {cfg.scope}. Mode: {cfg.mode}. Contract files: {contracts}. Frozen files: {frozen}. "
            "After each edit a background check runs old and new code on the same inputs; differences arrive as counterexamples. "
            "Available guard tools: impact, contract, diff_report (MCP server guard).")


def handle(event: dict):
    from guardlib import bootstrap
    messages = []
    if os.environ.get("ANTHROPIC_API_KEY"):
        messages.append(API_KEY)
    if _common.BOOT_ERROR:
        messages.append(f"LegacyGuard could not install its dependencies ({_common.BOOT_ERROR}); the guard is inactive. "
                        f"Install by hand: {bootstrap.manual_command(PLUGIN_ROOT)}")
        return hook_output("SessionStart", system_message=" ".join(messages))

    from guardlib import config as cfgmod
    from guardlib.paths import find_root
    root = find_root(event.get("cwd") or os.getcwd())
    try:
        cfg = cfgmod.load_config(root)
    except cfgmod.ConfigMissing:
        messages.append(SETUP)
        return hook_output("SessionStart", system_message=" ".join(messages))
    except cfgmod.ConfigError as exc:
        messages.append(f"LegacyGuard is inactive: .legacyguard/config.yaml is invalid ({exc}).")
        return hook_output("SessionStart", system_message=" ".join(messages))

    try:
        notice = start_session(cfg, event)
        if notice:
            messages.append(notice)
    except Exception as exc:  # noqa: BLE001 - a failed baseline must not take the summary down with it
        log_error(root, f"session_start: {exc!r}")
    return hook_output("SessionStart", context=summary(cfg), system_message=" ".join(messages) or None)


def start_session(cfg, event):  # replaced in T4.1
    return None


if __name__ == "__main__":
    run_hook(handle, install=True, needs_deps=False)
