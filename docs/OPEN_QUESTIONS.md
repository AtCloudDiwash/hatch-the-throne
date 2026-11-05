# OPEN_QUESTIONS.md — Unresolved Discussions

Rule: **never silently resolve an item here.** When one is decided, move it to [DECISIONS.md](DECISIONS.md) with a new entry and mark it resolved here.

## 1. Blocking (decide before the named milestone)

| ID | Question | Blocks | Evidence that settles it |
| --- | --- | --- | --- |
| OQ-B1 | Does django-oscar's test suite pass locally on SQLite, and what share of its offer/basket functions can run in isolation? | M7, D-014 | Spikes T0.1, T0.2. Fallback: OpenFisca |
| OQ-B2 | **Resolved → D-024 (default for one-pass build; revisit after demo).** How is a behavior difference labeled "requested" when the prompt asked for it? Options discussed: in-session Claude decides with the developer having the final say; developer marks it via waive; an optional prompt hook at Stop. Simple keyword matching was never agreed. | M5 (FR-16) | Team decision; T0.3 results |
| OQ-B3 | **Resolved → D-025 (default for one-pass build; revisit after demo).** Does the behavioral diff compare against the **session baseline** or the **previous edit**? Also how to treat a dirty working tree at session start. Both a PreToolUse snapshot and a baseline `git worktree` were mentioned. | M4, M5 | Team decision; recommendation in conversation leaned toward baseline worktree |
| OQ-B4 | **Resolved → D-026 (default for one-pass build; revisit after demo).** How does the guard find the target project's Python interpreter and dependencies (config key, auto-detect `.venv`, etc.)? | M5 | Team decision; test on billing-api and django-oscar |
| OQ-B5 | Verify on the pinned Claude Code version: `asyncRewake` exit-2 wake-up; whether an async hook's stdout JSON (success `additionalContext`, or the `systemMessage` notice to the developer that D-013 assumes) is honored; Stop `decision: "block"` and `stop_hook_active`; `ask` label in prompts; `-p` deny behavior. The hooks reference was only partly read. Also pick the minimum Claude Code version. | M1–M6 | Spike T0.3 |
| OQ-B6 | Approval to start: no milestone is approved. Also, the project's "Project Knowledge" doc (Nov 3) says no idea is selected, which conflicts with the master prompt (Nov 4). Update or confirm. | M0 | Team says "approved" for M0; team updates the stale doc |

## 2. Non-blocking

| ID | Question | Notes |
| --- | --- | --- |
| OQ-N1 | **Resolved → D-027 (default for one-pass build; revisit after demo).** Product name | "LegacyGuard"/`legacyguard` is a working name |
| OQ-N2 | **Resolved → D-028 (default for one-pass build; revisit after demo).** "Never again" storage mix: pinned tests, rules file, mined rules. Where pinned tests live (`tests/guard/test_pinned_<id>.py` was proposed) | Master prompt lists this as open |
| OQ-N3 | **Resolved → D-029 (default for one-pass build; revisit after demo).** Should the behavioral diff compare side effects (DB writes, file writes, logs), not just return values and exceptions? | Master prompt mentions side effects; mechanism not designed |
| OQ-N4 | **Resolved → D-030 (default for one-pass build; revisit after demo).** How the indexer finds the framework app object to list routes in each repo (FastAPI app path, Django settings module) | Probably a config key |
| OQ-N5 | **Resolved → D-031 (default for one-pass build; revisit after demo).** Which Python MCP library to use for the stdio server | Only "stdio, Python" agreed |
| OQ-N6 | **Resolved → D-032 (default for one-pass build; revisit after demo).** Guard on/off comparison: custom `claude -p` harness or `claude plugin eval`; how many runs plans can afford | Spike T0.4 |
| OQ-N7 | **Resolved → D-033 (default for one-pass build; revisit after demo).** Sizes and targets: number of A/B tasks, number of django-oscar commits to replay, target catch rate | Not set |
| OQ-N8 | **Resolved → D-034 (default for one-pass build; revisit after demo).** Should frozen files still be denied in advisory mode? | Policy table leaves this open |
| OQ-N9 | **Resolved → D-035 (default for one-pass build; revisit after demo).** Baseline worktree cleanup and reuse across sessions | Not discussed |
| OQ-N10 | Pitch lead: everyday agent safety or legacy modernization | Master prompt open decision |
| OQ-N11 | Team roles for the "Team" rubric criterion | Not provided |
| OQ-N12 | GitHub org/repo for the marketplace | Not provided |
| OQ-N13 | Windows testing coverage | Path normalization agreed; testing not planned |
| OQ-N14 | PreToolUse on `Bash` for file-mutating commands (FR-13) | Proposed for the future; Stop audit covers MVP |
| OQ-N15 | **Resolved → D-036 (default for one-pass build; revisit after demo).** Confirm FastAPI + SQLite for billing-api | Proposed, not explicitly confirmed |
| OQ-N16 | Status line integration (FR-26) | Optional polish |

## 2a. Evidence and conflicts recorded during the one-pass build

Each item is labeled **measured**, **observed once**, or **inferred**.

### Evidence (M0, 2026-11-05)

**OQ-B1, django-oscar on SQLite (measured).** At commit a5ed3c9 (v4.2.2), Python 3.12, Django 6.1.3, `DATABASE_ENGINE=django.db.backends.sqlite3 DATABASE_NAME=:memory: pytest tests -n 4`: 1,803 passed, 7 failed, 2 skipped, 70 s. The docs' `--sqlite` option no longer exists; the test settings read environment variables, and PostgreSQL is the default. Failures are in checkout thank-you views, category moves and concurrent order placement, none in offer or basket pricing. **The OpenFisca fallback is not triggered.** License: BSD-style "Redistribution and use" text confirmed in LICENSE (measured).

**OQ-B1, runnable-function share (measured).** Method (`spikes/t02_runnable.py`): for all 367 `def`s in `oscar/apps/offer` and `oscar/apps/basket`, with Django's dummy DB backend and sockets blocked, construct the class with no arguments where needed and try 10 naive argument tuples. Result: 28 of 367 (7.6%) returned a value; 142 of 367 (38.7%) ran at all, counting application exceptions as running. By kind: model methods 5 ok, 33 raised, 4 hit the DB, 159 no instance; plain methods 18 ok, 25 raised, 35 no instance; module-level 18 raised; view/form methods 5 ok, 38 raised, 3 DB, 24 no instance. Blockers: abstract models that cannot be constructed, and methods that need populated model instances (basket, lines, offers). **Implication (inferred):** most oscar functions will be reported `Untested`, so the backtest's catch rate depends on the planted bugs' location and on harvested inputs.

**OQ-B5, hook behavior on Claude Code v2.1.318, `claude -p`, model haiku (each observed once; `spikes/t03_hookspike/`):**

| Behavior | Result |
| --- | --- |
| `asyncRewake` exit 2 wakes Claude with stderr | Confirmed. Claude quoted the stderr token, labeled as a hook blocking error |
| Async hook stdout JSON reaches Claude | Confirmed for both `additionalContext` and `systemMessage`. The debug log shows `Found sync response from async_hook_*`, then an attachment. The docs say neither field is shown to the developer |
| `additionalContext` on PreToolUse | Confirmed on allow, deny and ask |
| `-p` turns an unanswerable `ask` into a deny | Confirmed. `permission_denied` with `decision_reason_type: hook`; Claude read the reason |
| Stop `decision: "block"` + `stop_hook_active` | Confirmed. First call false and Claude continued; second call true and the turn ended |
| `ask` prompt label `[plugin:legacyguard]` | Not checkable headless; documented behavior. See docs/MANUAL_CHECKS.md |
| Exec form with `args` and `${CLAUDE_PLUGIN_ROOT}` | Confirmed; `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PLUGIN_DATA` are also in the hook environment |
| SessionStart input lacks `permission_mode` | Observed once; the spec's common fields should not be assumed on every event |

**Minimum Claude Code version (decided in T8.1): v2.1.318**, the only version every behavior here was observed on. Docs give lower floors for single features (`onFailure` v2.1.295), but these were not tested.

**No M0 hook fallback is triggered.** Per the docs (inferred, not tested): in `-p` an async hook still running at teardown is killed, so a diff still in flight when Claude stops is covered only by the synchronous Stop audit. Also from the docs: an async hook's `systemMessage` goes to Claude, not the developer, so the D-013 "notice to the developer" must come from the Stop report and `/legacyguard:status`.

**OQ-N6, plan usage (measured, one run each).** Small Sonnet coding task: 26 s, 9 turns, 196k cache-read and 18.6k cache-write tokens, 1.7k output, $0.11 notional on a subscription login. Hook spike on Haiku: 32 s, 8 turns, $0.007 notional. `/usage` works in `claude -p` and did not move visibly (session 8%, week 10% before and after). **Estimate (inferred):** an A/B task at 3–5× the small task costs about $0.5 notional, so 20 runs are about $10 notional, which fits one Max window. Runs use Sonnet to conserve the plan.

**`claude plugin eval` (measured, once).** Works: 3 runs by default, regex grader passed, 5 s. Each run starts in an empty directory, and a case's workspace comes from scaffolding. The custom harness stays per D-032, because held-out trap checks need a seeded billing-api clone with its history.

**Observation (observed once).** In the usage trial Claude reported "the sandbox blocked pytest". The real cause was a permission denial: Claude ran `python -m pytest` and the allowlist only named `python3` and `pytest`. No sandbox is configured. The A/B allowlist must include all interpreter spellings.

## 3. Future research

- Precise references via a Python language server for edited functions only, if name matches are noisy.
- MELT-style mined transformation rules for durable "never again" (paper in project files).
- Legacy mode: business rules extracted from COBOL/PL/I code as invariants (paper in project files); migration verification.
- Mocking external services so more functions become runnable; DockerizeMe-style environment inference.
- Support for Copilot and Cursor.
- Evidence on the dollar cost of agent regressions and agent vs. human regression rates (none found so far).
- The AITest 2026 multi-agent change-impact paper (full text not found; do not cite its results).

## 4. Assumptions to validate

| Assumption | How to check |
| --- | --- |
| Target users have Claude Code on Pro or Max | Stated by the team; confirm with a few target developers |
| Pro/Max plans allow enough `claude -p` runs for evaluation | Spike T0.4 |
| A useful share of backend functions can run in isolation | Spike T0.2 |
| Name matching is precise enough for risk ranking | Backtest (M7) |
| D-013 alarm targets are attainable | Backtest (M7) |
| Current Claude Code models still cause regressions on a TDAD-style task set | Master prompt experiment 2; A/B (M7) |
| Behavioral diff beats TDAD-selected tests on recall without too many false alarms | Master prompt experiment 3 |
| Developers accept up to 3 prompts per session | User feedback during demo testing |
| django-oscar's license allows this use (believed BSD) | Check its LICENSE file during T0.1 |

## 5. Missing context (known gaps in the source conversation)

- The first message included a hand-drawn sketch (Frontier Model → Hook → Agentic System → Agent Feedback). It is the basis of D-002; no other details were in it.
- The "Road Above the Clouds" interactive was referenced by link in the master prompt but not read in this conversation.
- The Nov 3 research conversation is known only through the master prompt's summary.
- The Claude Code hooks reference was read in part (about 70% initially); see OQ-B5.
- The Backend Guard Map artifact (claude.ai) is a visual summary of this same conversation, not an additional source.
