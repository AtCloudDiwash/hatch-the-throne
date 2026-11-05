# CLAUDE.md — Guardrails for AI Coding Agents (working name: LegacyGuard)

> **Status: architecture defined, implementation NOT approved.**
> Do not write product code until the team explicitly says "approved" for a specific milestone in [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md). Completing one milestone never approves the next.

## What this project is

A Claude Code **plugin** that acts as a guardrail for Claude Code while it edits a **single Python backend service**. It does not try to find the one "right" change. It stops changes that break existing behavior, contracts or tests, feeds concrete evidence back to Claude so Claude can turn back, and keeps the developer in control.

Core belief: **the LLM proposes; execution decides.** The central check is a **behavioral diff**: run the old and new versions of each changed function on the same inputs and report every input where results differ.

Built for the University of Southern Mississippi Hatchathon 2026 (Legacy Tech track, November 2–9, 2026). The long-term market is verification for legacy modernization.

"LegacyGuard" / `legacyguard` is a **working name only**. The product name is unresolved.

## Documentation map

| File | Read it when |
| --- | --- |
| [docs/PRODUCT.md](docs/PRODUCT.md) | You need the problem, users, value, MVP boundary or non-goals |
| [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) | You implement or test a feature (requirement IDs `FR-*`, `NFR-*`) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | You touch hooks, the indexer, the diff runner, the MCP server or data flow |
| [docs/TECH_STACK.md](docs/TECH_STACK.md) | You add a dependency or rely on a Claude Code behavior |
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | You start any task (task IDs `T*`) |
| [docs/DECISIONS.md](docs/DECISIONS.md) | You are about to change a design choice, or reintroduce a rejected idea |
| [docs/TESTING.md](docs/TESTING.md) | You write tests or verify a milestone |
| [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md) | Something is ambiguous. Ask; never silently resolve |

## Stack summary (confirmed)

- Python 3.10+ for every guard component; local only.
- Claude Code plugin: hooks (`hooks/hooks.json`), a stdio MCP server (`.mcp.json`), skills (slash commands).
- SQLite for the guard index and session state.
- tree-sitter, git, coverage.py (per-test contexts), Hypothesis.
- No Anthropic API key. The only model is Claude Code running on the user's Pro/Max plan.

Details and constraints: [docs/TECH_STACK.md](docs/TECH_STACK.md).

## Planned repository layout (proposed; not yet created)

```text
legacyguard/                      # the plugin
├── .claude-plugin/plugin.json
├── hooks/hooks.json              # SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop
├── .mcp.json                     # guard MCP server (stdio, Python)
├── skills/                       # index, status, impact, waive, pin, mode
├── scripts/                      # session_start.py, prompt_context.py, pre_edit.py, post_edit.py, stop_audit.py
├── indexer/                      # tree-sitter + git + coverage + routes → SQLite
└── runner/                       # behavioral diff runner
demo/billing-api/                 # controlled demo repo (FastAPI + SQLite, proposed)
eval/                             # A/B harness and django-oscar backtest
```

Inside a guarded target repo, the guard writes only under `.legacyguard/` (`config.yaml`, `index.db`, `baseline/` worktree, `waivers.json`, `session.json`, `reports/`).

## Non-negotiable constraints

1. **Never call the Anthropic API** and never require an API key. Warn if `ANTHROPIC_API_KEY` is set (it switches Claude Code to per-token billing).
2. **Only evidence can interrupt a person.** Static and history signals go to Claude as context only. See [DECISIONS D-013](docs/DECISIONS.md).
3. Every finding has exactly one status: **Verified pass**, **Confirmed failure**, **Behavior difference — intent unknown**, **Potential risk (static only)**, **Untested**.
4. Never claim a change is "safe". Say what was checked and what was not.
5. Never auto-approve, merge, deploy, or pin a regression test without the developer.
6. Never modify the developer's prompt.
7. No single "health score".
8. The model that proposes inputs or intent never grades its own output; execution grades.
9. The behavioral diff runs with the **network blocked** and never touches real external services.
10. The guard never edits the developer's source files; it writes only under `.legacyguard/`.

## Coding standards and boundaries

- Hook scripts are **stateless processes**: read JSON from stdin, read SQLite, print **one JSON object** on stdout, exit 0. Use exit 2 only for the async behavioral-diff wake-up. On any internal error, fail open: log, exit 0, print nothing. Nothing else on stdout.
- Keep each `additionalContext` under about 1,500 characters (Claude Code caps it at 10,000).
- Write context as factual statements, never as imperative "SYSTEM:" commands (they can trigger prompt-injection defenses).
- PreToolUse must finish in about one second. Slow work belongs in the async PostToolUse hook or at Stop.
- Normalize Windows path separators before comparing paths.
- Use exec form (`command` + `args`) with `${CLAUDE_PLUGIN_ROOT}` for hook commands.
- Every finding records its source (`names`, `tests`, `routes`, `history`, `diff`) so a static guess never poses as proof.

## Workflow for each task

1. Confirm the milestone is approved. If not, stop and ask.
2. Read the task in [IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) and the linked requirements.
3. Write tests first where practical ([TESTING.md](docs/TESTING.md)).
4. Implement; run `claude plugin validate ./legacyguard` and the unit tests.
5. Verify hooks live with `claude --plugin-dir ./legacyguard` and `claude --debug-file <path>`.
6. Record any new decision in [DECISIONS.md](docs/DECISIONS.md) and any new ambiguity in [OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md).
