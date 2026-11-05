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
