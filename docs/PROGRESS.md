# PROGRESS

Rendered from `docs/progress_state.json` by `tools/progress.py`. To resume after an interruption, read this file and `docs/devlog.jsonl`, then continue from the first task not marked done.

- **Current milestone and task:** M1 / T1.4
- **Next step:** SessionStart basics.

## Status

| Task | Milestone | Status | Title | Dev log | Commit |
| --- | --- | --- | --- | --- | --- |
| T0.0 | M0 | done | [x] Setup: docs, progress, dev log tools, default decisions | DL-001 DL-002 DL-003 DL-004 DL-005 DL-006 DL-007 DL-008 DL-009 DL-010 DL-011 DL-012 DL-013 DL-014 DL-015 | 121c203 |
| T0.1 | M0 | done | [x] django-oscar on SQLite (OQ-B1) | DL-016 | b9dcf7d |
| T0.2 | M0 | done | [x] Runnable-function share (OQ-B1) | DL-017 | 702ea9c |
| T0.3 | M0 | done | [x] Hook behavior check (OQ-B5, NFR-10) | DL-018 | fbb3000 |
| T0.4 | M0 | done | [x] Plan usage of headless runs (OQ-N6) | DL-019 | 63a2461 |
| T1.1 | M1 | done | [x] Manifest and wiring | DL-020 DL-021 | 3e3cf94 |
| T1.2 | M1 | done | [x] Shared hook runtime | DL-022 DL-023 | baea1b9 |
| T1.3 | M1 | done | [x] Bootstrap (FR-03) | DL-024 DL-025 |  |
| T1.4 | M1 | pending | [ ] SessionStart basics (FR-10 steps 5-6) |  |  |
| T2.1 | M2 | pending | [ ] billing-api service |  |  |
| T2.2 | M2 | pending | [ ] Planted traps |  |  |
| T2.3 | M2 | pending | [ ] Planted history |  |  |
| T2.4 | M2 | pending | [ ] A/B task set |  |  |
| T3.1 | M3 | pending | [ ] Names table (FR-04) |  |  |
| T3.2 | M3 | pending | [ ] Coverage map (FR-05) |  |  |
| T3.3 | M3 | pending | [ ] Routes and contracts (FR-06) |  |  |
| T3.4 | M3 | pending | [ ] Co-change (FR-07) |  |  |
| T3.5 | M3 | pending | [ ] Incremental re-index (FR-08) |  |  |
| T3.6 | M3 | pending | [ ] Impact library (FR-09) |  |  |
| T3.7 | M3 | pending | [ ] MCP impact tool and index/impact skills (FR-21, FR-22) |  |  |
| T4.1 | M4 | pending | [ ] Baseline worktree and session state (FR-10) |  |  |
| T4.2 | M4 | pending | [ ] UserPromptSubmit context (FR-11) |  |  |
| T4.3 | M4 | pending | [ ] Virtual apply and symbol diff (FR-12) |  |  |
| T4.4 | M4 | pending | [ ] Contract and test-integrity checks (FR-12, FR-17) |  |  |
| T4.5 | M4 | pending | [ ] Decision policy, modes, budget (FR-12, FR-20, FR-23) |  |  |
| T4.6 | M4 | pending | [ ] Frozen and scope rules |  |  |
| T5.1 | M5 | pending | [ ] Runner subprocesses (FR-14) |  |  |
| T5.2 | M5 | pending | [ ] Network block (FR-14) |  |  |
| T5.3 | M5 | pending | [ ] Input sources (FR-14) |  |  |
| T5.4 | M5 | pending | [ ] Self-diff filter (FR-14) |  |  |
| T5.5 | M5 | pending | [ ] Untested classification (FR-14) |  |  |
| T5.6 | M5 | pending | [ ] PostToolUse wake-up (FR-15, FR-16) |  |  |
| T6.1 | M6 | pending | [ ] Stop audit (FR-18) |  |  |
| T6.2 | M6 | pending | [ ] Report (FR-19) |  |  |
| T6.3 | M6 | pending | [ ] Waive and mode skills (FR-24, FR-23) |  |  |
| T6.4 | M6 | pending | [ ] Pin (FR-25) |  |  |
| T6.5 | M6 | pending | [ ] Status skill and remaining MCP tools (FR-21, FR-22) |  |  |
| T7.1 | M7 | pending | [ ] Backtest harness (FR-28) |  |  |
| T7.2 | M7 | pending | [ ] Seeded bugs (FR-28) |  |  |
| T7.3 | M7 | pending | [ ] Guard on/off (FR-29) |  |  |
| T7.4 | M7 | pending | [ ] Budget check (D-013) |  |  |
| T8.1 | M8 | pending | [ ] Pin minimum Claude Code version (NFR-10) |  |  |
| T8.2 | M8 | pending | [ ] Live E2E-1 to E2E-8 |  |  |
| T8.3 | M8 | pending | [ ] Dry-run steps, backup video, names and roles |  |  |
| T8.4 | M8 | pending | [ ] Final report |  |  |

## Milestone summaries

### M0

1. django-oscar runs on SQLite: 1,803 passed, 7 failed, 70 s, none of the failures in pricing code.
2. Only 7.6% of 367 offer/basket functions return a value in isolation; 38.7% run at all.
3. Every headless-testable hook behavior was confirmed on v2.1.318, so no fallback triggered.
4. A/B estimate is about $10 notional for 20 Sonnet runs; plugin eval works but the custom harness stays.
5. The prompt label needs a person, so it is MC-1 in MANUAL_CHECKS.md.


## Evidence

### T0.0 Setup: docs, progress, dev log tools, default decisions (done)

```text
$ .venv/bin/pytest -q tests/tools
....                                                                     [100%]
4 passed in 0.47s
(exit 0)
```

### T0.1 django-oscar on SQLite (OQ-B1) (done)

```text
$ DATABASE_ENGINE=django.db.backends.sqlite3 DATABASE_NAME=:memory: pytest tests -q -n 4
7 failed, 1803 passed, 2 skipped, 3721 warnings, 104 subtests passed in 69.07s (0:01:09)
FAILED: 3 checkout ThankYouView, 2 catalogue category moves, 2 concurrent order placement. None in offer or basket pricing.
```

### T0.2 Runnable-function share (OQ-B1) (done)

```text
$ python spikes/t02_runnable.py   (in the oscar checkout, DB dummy backend)
{"total_defs": 367, "returned_value": 28, "ran_including_app_exceptions": 142, "share_returned": 0.076, "share_ran": 0.387,
 "by_kind": {"model-method": {"noinstance": 159, "raises": 33, "db": 4, "ok": 5}, "plain-method": {"noinstance": 35, "raises": 25, "ok": 18}, "module-level": {"raises": 18}, "view/form-method": {"noinstance": 24, "ok": 5, "raises": 38, "db": 3}}}
```

### T0.3 Hook behavior check (OQ-B5, NFR-10) (done)

```text
$ claude --version
2.1.318 (Claude Code)
$ claude -p "$PROMPT" --plugin-dir spikes/t03_hookspike --model haiku --permission-mode acceptEdits ... --debug-file debug.txt
debug: Hook PreToolUse returned permissionDecision: deny (reason: LGTOKEN-DENYREASON)
debug: Hook PreToolUse returned permissionDecision: ask (reason: LGTOKEN-ASKREASON)
stream: permission_denied decision_reason_type=hook decision_reason=LGTOKEN-ASKREASON
debug: Hooks: Found sync response from async_hook_86348: {"systemMessage":"LGTOKEN-ASYNCSYS",...,"additionalContext":"LGTOKEN-ASYNCCTX"}
debug: Hook PostToolUse:Write error: status code 2 stderr: LGTOKEN-REWAKE-STDERR
hooklog: stop active=False, then stop active=True
Claude listed: SESSIONCTX, PROMPTCTX, PRECTX, DENYREASON, DENYCTX, ASKREASON, ASKCTX, REWAKE-STDERR, ASYNCSYS, ASYNCCTX; then STOPREASON
```

### T0.4 Plan usage of headless runs (OQ-N6) (done)

```text
$ claude -p <small task> --model sonnet --output-format json
{"subtype":"success","num_turns":9,"duration_ms":25965,"total_cost_usd":0.1095}  cache_read=178028 cache_create=18598 output=1725
$ claude -p /usage
Current session: 8% used; Current week (all models): 10% used (unchanged after the runs)
$ claude plugin eval . --ablation none --trust-plugin
smoke score 1.00 (3 runs) $0.00; 1 case(s), 5s
```

### T1.1 Manifest and wiring (done)

```text
$ claude plugin validate ./legacyguard

✔ Validation passed
(exit 0)
```

### T1.2 Shared hook runtime (done)

```text
$ .venv/bin/pytest -q tests/test_runtime.py
.....................                                                    [100%]
21 passed in 0.81s
(exit 0)
```

### T1.3 Bootstrap (FR-03) (done)

```text
$ cat /tmp/lg_t13.txt && .venv/bin/pytest -q tests/test_bootstrap.py tests/test_session_start.py::test_bootstrap_failure_produces_manual_command
--- first start (clean data dir, real pip)
{"hookSpecificOutput": {"additionalContext": "LegacyGuard is active. Scope: .. Mode: guarded. Contract files: none. Frozen files: none. After each edit a background check runs old and new code on the same inputs; differences arriv

--- second start
{"hookSpecificOutput": {"additionalContext": "LegacyGuard is active. Scope: .. Mode: guarded. Contract files: none. Frozen files: none. After each edit a background check runs old and new code on the same inputs; differences arriv
....                                                                     [100%]
4 passed in 2.74s
(exit 0)
```

