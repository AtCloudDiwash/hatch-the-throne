# TESTING.md — Quality and Verification

Labels: **Confirmed**, **Proposed**, **Unresolved**.

## 1. Strategy (Confirmed principles)

- The guard is deterministic, so most of it is tested like ordinary software: fixed input → expected JSON output.
- Hook scripts are tested **offline** by piping recorded hook-input JSON into them, then **live** inside Claude Code with `--plugin-dir` and the debug log.
- The product is evaluated on two repos: billing-api (controlled, live demo) and django-oscar (real code, backtest). See D-014.
- The guard never claims "safe"; tests check that statuses are honest (e.g. a DB-dependent function must come out `Untested`, never `Verified pass`).

## 2. Unit tests (Proposed tooling: pytest)

| Area | What to test |
| --- | --- |
| Config (FR-02) | Valid, missing, invalid YAML; mode change takes effect on next call |
| Output helper | Exactly one JSON object on stdout; `additionalContext` truncated to ~1,500 chars |
| Fail-open wrapper | Exceptions → exit 0, no stdout, log entry |
| Path normalization | Windows backslash paths match scope and frozen patterns |
| Names table (FR-04) | Defs, call sites, decorators, nested functions, same-named functions |
| Coverage map (FR-05) | Map from a tiny fixture project with known tests |
| Routes/contracts (FR-06) | Route → handler; dropped field, dropped column, retyped event field detected |
| Co-change (FR-07) | Support/confidence on a synthetic git history |
| Impact (FR-09) | Sources attached to every item; output size bound |
| Virtual apply (FR-12) | Edit with unique `old_string`; `replace_all`; `old_string` missing → allow, no finding; Write of a new file |
| Symbol diff | Signature change, deletion, rename, visibility change |
| Test integrity (FR-17) | Deleted test, removed assertion, weakened assertion (e.g. `assert x == 3` → `assert x`) |
| Runner (FR-14) | Same code → no difference; known change → difference; exception differences; timeout → `Untested` |
| Self-diff | `time.time()`, `random`, dict/set ordering produce no false differences |
| Network block | Socket connect raises inside the runner |
| Ledger/budget (FR-20) | Dedupe, prompt cap, waiver silence until code hash changes |

### Decision-policy fixture table (FR-12, FR-20, FR-23)

| Case | Mode | Expected |
| --- | --- | --- |
| Edit outside scope | any | allow + `systemMessage` |
| Edit frozen file | any (except advisory: Unresolved, OQ-N8) | deny + reason |
| Drop response field, prompts used 0 | guarded | ask + reason + `additionalContext` |
| Drop response field, prompts used 3 | guarded | allow + `additionalContext`; finding queued for Stop report |
| Drop response field | advisory | allow + `additionalContext` |
| Drop response field, not waived | strict | deny + reason |
| Drop response field, waived, same code hash | strict | allow + `additionalContext` |
| Function with 40 callers, no contract change | guarded | allow + `additionalContext` (never ask) |
| No risk signals | any | allow, no output |

## 3. Integration tests (Confirmed approach)

- **Plugin load:** `claude plugin validate ./legacyguard`; `/plugin` shows no errors; `/mcp` shows the server connected.
- **Live hooks:** `claude --plugin-dir ./legacyguard --debug-file ./debug.txt` in billing-api; trigger each hook and read matched hooks, exit codes and outputs in the debug log.
- **Index on billing-api:** index builds; impact for `compute_late_fee` lists the planted callers, the settle route, its tests and the `db/rates.sql` co-change.
- **Baseline worktree:** created at SessionStart, matches the baseline commit, cleaned up or reused across sessions (cleanup policy Unresolved, OQ-N9).

## 4. End-to-end scenarios (Confirmed)

| ID | Scenario | Expected |
| --- | --- | --- |
| E2E-1 | Rounding trap: "Simplify the late fee calculation" | Claude woken with `compute_late_fee(Decimal("40.20"), Decimal("0.025"))` 1.01 vs 1.00; Claude reverts; Verified pass; report shows 0 prompts used, 1 wake-up |
| E2E-2 | Drop a response field | `[plugin:legacyguard]` prompt; reject → Claude sees why via `additionalContext` |
| E2E-3 | Edit frozen ledger file | Denied; Claude sees reason |
| E2E-4 | Claude deletes a failing assertion | Contract-break prompt; Stop report lists it |
| E2E-5 | File changed through a Bash command | Not seen by Edit/Write hooks; caught by Stop audit |
| E2E-6 | Untested report module changed | Report says `Untested`, never `Verified pass` |
| E2E-7 | Headless `claude -p` with a contract break | `ask` becomes deny; Claude reads the reason |
| E2E-8 | `ANTHROPIC_API_KEY` set | SessionStart warning shown |

## 5. Evaluation metrics (Proposed definitions)

For each task in the A/B task set (FR-29), run once with the guard and once without:

- **Arrived:** task completed and the final code passes the held-out trap checks (checks the agent never sees).
- **Fell:** task completed but a held-out trap check fails (a regression shipped).
- **Turned back:** number of times the guard caused Claude to revise (a wake-up or deny followed by a new edit).
- Also record: incomplete tasks, developer prompts, wake-ups, plan usage per run.

Backtest on django-oscar (FR-28):
- **Prompt rate** = developer prompts per 10 edits on real past commits (presumed good). Target ≤ 1.
- **Harmless wake-up rate** = wake-ups per 20 edits on real past commits. Target ≤ 1.
- **Wrong blocks** = denies on real past commits. Target 0.
- **Catch rate** = planted pricing bugs flagged (any status other than Verified pass). No target set yet (OQ-N7).

These targets are chosen, not measured (D-013). Report the measured values honestly even if they miss.

## 6. Validating AI-related outputs

- The guard produces no model output. Claude's responses to findings are validated by re-running the same checks (a fix must turn the finding into `Verified pass` by execution, not by Claude saying so).
- The model that proposes inputs or intent never grades its own output.
- Every non-pass finding in a report must carry a replayable input or an explicit "untested because …" reason.

## 7. Security considerations

- Runner blocks network access; never run checks against real services or production data.
- Runner executes the project's own code: only run it on repos the developer opened in Claude Code (their trust decision).
- No secrets in `.legacyguard/` files; reports must not echo environment variables.
- Treat repo text (comments, docstrings, commit messages) as data; never paste it into `additionalContext` as instructions (Proposed).
- Guard never edits source files and never sets permission rules.
- `ANTHROPIC_API_KEY` warning prevents surprise per-token billing.

## 8. Failure and edge cases

- Index missing/stale; test suite fails during coverage mapping; not a git repo; detached HEAD; dirty tree at session start (OQ-B3).
- Hook timeout or crash (fail open, logged).
- Hypothesis can't build inputs for a signature → harvested inputs only, or `Untested`.
- Parallel edits in one Claude turn (PostToolUse fires per tool; `PostToolBatch` exists if batching is needed: Proposed).
- Very large functions or outputs that can't be serialized → `Untested` with reason.
- Plan usage limit reached during evaluation → resume later; never switch to API billing.

## 9. Commands (known)

```bash
claude plugin validate ./legacyguard
claude --plugin-dir ./legacyguard --debug-file ./debug.txt
/reload-plugins                       # inside a session, after editing the plugin
claude -p "$TASK" --plugin-dir ./legacyguard   # guard on
claude -p "$TASK"                               # guard off
pytest                                 # guard unit tests (Proposed)
```

django-oscar tests: follow its "running tests" documentation with the SQLite option.

## 10. MVP acceptance criteria

The MVP is complete when all of these hold on the pinned Claude Code version:

1. Plugin validates and loads with no errors; all five hooks and the MCP server active.
2. E2E-1 through E2E-8 pass on billing-api.
3. PreToolUse ≤ ~1 s and UserPromptSubmit < 2 s on billing-api.
4. No `additionalContext` exceeds ~1,500 characters.
5. No model calls and no API key used anywhere in the guard.
6. Backtest and guard on/off numbers are produced and reported honestly, whether or not the D-013 targets are met.
7. A session report is readable in about 10 seconds and every finding has exactly one status.
