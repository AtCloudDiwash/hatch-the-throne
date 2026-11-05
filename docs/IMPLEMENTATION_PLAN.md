# IMPLEMENTATION_PLAN.md — Development Roadmap

> **M0 to M8 were approved for one continuous run, now complete (docs/FINAL_REPORT.md).** After that run, each milestone needs an explicit "approved" from the team before work starts. Finishing a milestone never approves the next one.

Hackathon window: November 2–9, 2026. Requirements: [REQUIREMENTS.md](REQUIREMENTS.md). Test details: [TESTING.md](TESTING.md).

File paths below are the proposed layout from [CLAUDE.md](../CLAUDE.md); adjust if the team chooses differently.

## Milestone overview

| Milestone | Produces | Verifiable by | Covers |
| --- | --- | --- | --- |
| M0 Feasibility spikes | Answers to blocking questions; no product code | Written findings in OPEN_QUESTIONS.md | OQ-B1, B5, N6; NFR-10 |
| M1 Plugin skeleton | Plugin that loads, reads config, warns on API key | `claude --plugin-dir` session + debug log | FR-01, 02, 03, 10 (part) |
| M2 Demo repo | billing-api with traps and history | Its own test suite passes | FR-27 |
| M3 Index + impact | `index.db`, `impact()` via MCP and slash command | Impact output on billing-api | FR-04–09, 21 (impact), 22 (index, impact) |
| M4 Pre-write guard | Context before planning; allow/ask/deny before writes | Scripted hook-input fixtures + live session | FR-10, 11, 12, 17 (pre), 20, 23 |
| M5 Behavioral diff | Old vs. new runner; Claude woken with counterexamples | Rounding trap caught live | FR-14, 15, 16 |
| M6 Stop audit + controls | Report, block-once, waive, pin, mode, status | End-to-end session report | FR-17 (Stop), 18, 19, 21, 22, 24, 25 |
| M7 Evaluation | Backtest and guard on/off numbers | Metrics files | FR-28, 29 |
| M8 Demo readiness | Pinned version, polished report, backup video | Dry-run pitch | NFR-10, PRODUCT §10 |

M2 can run in parallel with M1 if both are approved. M3 depends on M1 and M2.

---

## M0 Feasibility spikes (throwaway code only)

### T0.1 django-oscar on SQLite (OQ-B1)
- **Objective:** Confirm django-oscar's test suite runs locally on SQLite.
- **Details:** Clone; follow its "running tests" docs with the `--sqlite` option; record time and pass count.
- **Done:** Pass/fail recorded; if fail, try OpenFisca and record.
- **Verify:** Notes in OPEN_QUESTIONS.md updated.

### T0.2 Runnable-function share (OQ-B1)
- **Objective:** Estimate what share of functions in django-oscar's offer/basket code can be called in isolation with harvested or generated inputs.
- **Done:** A number with method described; list of blockers (DB, globals).

### T0.3 Hook behavior check on the pinned Claude Code version (OQ-B5, NFR-10)
- **Objective:** With tiny throwaway hooks, confirm: `asyncRewake` exit 2 wakes Claude with stderr; whether an async hook's stdout JSON reaches Claude; `ask` prompt label; `-p` turns unanswerable `ask` into deny; Stop `block` + `stop_hook_active`; `additionalContext` delivery on PreToolUse.
- **Done:** Each behavior marked confirmed/not, with the Claude Code version.

### T0.4 Plan usage of headless runs (OQ-N6)
- **Objective:** Run 2 tasks with `claude -p` and read `/usage`; try `claude plugin eval` once.
- **Done:** Estimated runs affordable per plan window; decision input for M7.

---

## M1 Plugin skeleton

### T1.1 Manifest and wiring
- **Files:** `legacyguard/.claude-plugin/plugin.json`, `hooks/hooks.json`, `.mcp.json`, `scripts/*.py` (stubs).
- **Details:** Wire SessionStart, UserPromptSubmit, PreToolUse (`Edit|Write`), PostToolUse (`Edit|Write`, `async`, `asyncRewake`), Stop to stub scripts in exec form with `${CLAUDE_PLUGIN_ROOT}`. Stubs exit 0 with no output.
- **Done:** `claude plugin validate` passes; all hooks appear in `/hooks` with source `[plugin:legacyguard]`.
- **Tests:** none beyond validation.

### T1.2 Shared hook runtime
- **Files:** `legacyguard/scripts/_common.py`.
- **Details:** Read stdin JSON; load `config.yaml` (FR-02); fail-open wrapper (any exception → log, exit 0, no output); path normalization; single-JSON-object output helper; `additionalContext` length guard (~1,500 chars).
- **Done:** Unit tests pass for config parsing, fail-open, output shape.

### T1.3 Bootstrap (FR-03)
- **Details:** Create venv in `${CLAUDE_PLUGIN_DATA}`; install dependencies once; record a marker file.
- **Done:** Second session start skips install; failure produces a `systemMessage` with the manual command.

### T1.4 SessionStart basics (FR-10 steps 5–6)
- **Details:** API-key warning; context summary from config.
- **Done:** Live session shows the summary in Claude's context (check via debug log) and the warning when `ANTHROPIC_API_KEY` is set.

---

## M2 billing-api demo repo (FR-27)

### T2.1 Service
- **Files:** `demo/billing-api/` (app, `openapi.yaml`, `migrations/`, `schemas/events/`, `tests/`).
- **Details:** FastAPI + SQLite (Proposed; confirm at approval). Around 3,000 lines. Includes `billing/fees.py::compute_late_fee` using `Decimal.quantize(CENT, ROUND_HALF_UP)`.
- **Done:** Its test suite passes; openapi.yaml matches routes.

### T2.2 Planted traps
- Banker's rounding (fees), shared date helper with many callers, nightly job (`jobs/close_month.py`) calling the fee function, untested report (`reports/aging.py`), frozen ledger file (`legacy/ledger_v1.py`).
- **Done:** Each trap documented in `demo/billing-api/TRAPS.md` with the edit that triggers it.

### T2.3 History
- **Details:** Commit history where `billing/fees.py` and `db/rates.sql` often change together.
- **Done:** `git log` shows the planted pattern.

### T2.4 Task set
- **Details:** Natural-language tasks for the A/B, each touching at least one trap. Count Unresolved (OQ-N7).
- **Done:** Tasks written in `eval/tasks/`.

---

## M3 Index and impact

| Task | Objective | Files | Done when |
| --- | --- | --- | --- |
| T3.1 | Names table (FR-04) | `indexer/names.py` | All defs and call sites of billing-api stored |
| T3.2 | Coverage map (FR-05) | `indexer/coverage_map.py` | Test → function map matches a manual check on 3 functions |
| T3.3 | Routes and contracts (FR-06) | `indexer/routes.py`, `indexer/contracts.py` | Every openapi route maps to a handler; migrations and event schemas parsed |
| T3.4 | Co-change (FR-07) | `indexer/history.py` | Planted pair reported with confidence |
| T3.5 | Incremental (FR-08) | `indexer/__main__.py` | One-file change re-parses one file |
| T3.6 | Impact library (FR-09) | `guardlib/impact.py` | Output example in FR-09 reproduced for `compute_late_fee`; ≤ ~1,500 chars |
| T3.7 | MCP `impact` tool + skills `/legacyguard:index`, `/legacyguard:impact` (FR-21, FR-22) | `mcp_server/`, `skills/` | `/mcp` connected; Claude calls `impact` successfully |

Tests: unit tests per table on small fixture repos; one integration test indexing billing-api.

---

## M4 Pre-write guard

| Task | Objective | Done when |
| --- | --- | --- |
| T4.1 | Baseline worktree + session state (FR-10 steps 2–4) | `.legacyguard/baseline/` at baseline commit; `session.json` reset |
| T4.2 | UserPromptSubmit context (FR-11) | Prompt naming `billing/fees.py` yields callers/routes/tests in context; < 2 s |
| T4.3 | Virtual apply + symbol diff (FR-12 step 3) | Fixture edits detect signature change, deletion, rename |
| T4.4 | Contract and test-integrity checks (FR-12 step 4, FR-17 pre) | Fixtures: dropped response field, dropped column, removed assertion → contract break |
| T4.5 | Decision policy + modes + budget (FR-12, FR-20, FR-23) | Fixture table in TESTING.md passes; 4th break in a session doesn't prompt |
| T4.6 | Frozen and scope rules | Frozen edit denied; out-of-scope edit allowed with notice |

Verify live: `claude --plugin-dir ./legacyguard` in billing-api; drop a response field → `[plugin:legacyguard]` prompt; edit frozen file → denied. PreToolUse ≤ ~1 s.

---

## M5 Behavioral diff

| Task | Objective | Done when |
| --- | --- | --- |
| T5.1 | Runner subprocesses on baseline vs. working tree (FR-14 step 2) | Same function, same input → identical result on unchanged code |
| T5.2 | Network block (FR-14 step 3) | A function that opens a socket raises inside the runner |
| T5.3 | Input sources: test-harvested + Hypothesis (FR-14 step 1) | ≥ 1 harvested and ≥ 1 generated input for `compute_late_fee` |
| T5.4 | Self-diff filter (FR-14 step 4) | A function returning `time.time()` yields no false difference |
| T5.5 | Untested classification (FR-14 step 6) | DB-dependent function reported `Untested` with reason |
| T5.6 | Async PostToolUse with wake-up (FR-15, FR-16) | Rounding trap: Claude woken with `Decimal("40.20")`, `Decimal("0.025")` → 1.01 vs 1.00; Claude reverts; re-check records Verified pass |

Prerequisite: OQ-B3 (baseline vs. previous edit) and OQ-B4 (target interpreter) decided.

---

## M6 Stop audit and developer controls

| Task | Objective | Done when |
| --- | --- | --- |
| T6.1 | Stop audit (FR-18) | Bash-made contract change caught; block once, never twice |
| T6.2 | Report (FR-19) | Report lists statuses, prompts used, wake-ups, pin suggestions; readable in 10 s |
| T6.3 | Waive (FR-24) + mode (FR-23) skills | Waived finding silent until code hash changes |
| T6.4 | Pin (FR-25) | Developer-invoked pin writes a regression test that fails on the bad version and passes on the good one |
| T6.5 | Status skill + remaining MCP tools (FR-21, FR-22) | `/legacyguard:status` and `contract`, `diff_report` tools work |

---

## M7 Evaluation

| Task | Objective | Done when |
| --- | --- | --- |
| T7.1 | Backtest harness (FR-28) | `legacyguard backtest` on N django-oscar commits outputs prompt rate, wake-up rate; N is set in OQ-N7 |
| T7.2 | Seeded bugs (FR-28) | Catch rate on planted pricing bugs reported |
| T7.3 | Guard on/off (FR-29) | Arrived / Turned back / Fell counts for the task set, both conditions, using `claude -p` (or `claude plugin eval` per T0.4) |
| T7.4 | Budget check (D-013) | Measured rates compared with targets; downgrade signals if missed |

Runs split across teammates' plans over two days.

---

## M8 Demo readiness

- Pin and document the minimum Claude Code version (NFR-10).
- Dry-run the 2.5-minute pitch with a live run; record a backup video.
- Fill product name, team roles, pitch lead (OPEN_QUESTIONS).

## M9 Session map (approved 2026-11-05, after the one-pass run)

| Task | Objective | Done when |
| --- | --- | --- |
| T9.1 | Map data and impact text tree (FR-30) | Model for billing-api's rounding edit has the changed function, its callers with test reach, edges marked observed or name-only, and the settle route; `/legacyguard:impact` prints a tree |
| T9.2 | HTML map, written at Stop, plus `/legacyguard:map` (FR-30) | Stop writes the `.html` next to the `.md`; a map failure leaves the report intact; the file works offline |
| T9.3 | Live check, browser check and docs | A live `claude -p` Stop writes the map; the map is checked in a browser in light and dark |

## Requirement → task traceability

| Requirement | Tasks |
| --- | --- |
| FR-01 | T1.1 |
| FR-02 | T1.2 |
| FR-03 | T1.3 |
| FR-04–08 | T3.1–T3.5 |
| FR-09 | T3.6 |
| FR-10 | T1.4, T4.1 |
| FR-11 | T4.2 |
| FR-12 | T4.3–T4.6 |
| FR-13 | Future (not planned) |
| FR-14 | T5.1–T5.5 |
| FR-15, FR-16 | T5.6 |
| FR-17 | T4.4, T6.1 |
| FR-18 | T6.1 |
| FR-19 | T6.2 |
| FR-20 | T4.5 |
| FR-21 | T3.7, T6.5 |
| FR-22 | T3.7, T6.3, T6.5 |
| FR-23 | T4.5, T6.3 |
| FR-24 | T6.3 |
| FR-25 | T6.4 |
| FR-26 | Future (not planned) |
| FR-27 | T2.1–T2.4 |
| FR-28 | T7.1, T7.2 |
| FR-29 | T7.3 |
| FR-30 | T9.1, T9.2, T9.3 |
