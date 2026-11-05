# DECISIONS.md — Architectural Decision Log

Status values: **Confirmed**, **Confirmed (provisional)** = decided at the team's request and pending validation, **Proposed**, **Rejected**, **Deferred**, **Unresolved**.

Rejected ideas are kept on purpose. **Do not reintroduce a rejected idea without a new decision entry.**

---

## D-001 Product direction: guardrails for AI coding agents
- **Context:** The team explored many ideas (InvisibleERP, LegacyTwin, AgentBoundary, …) before selecting one.
- **Options:** the ideas listed in the project's "Project Knowledge" doc.
- **Decision:** Guardrails for AI coding agents, built around the behavioral diff. Legacy modernization is the long-term market.
- **Reasoning:** Real, felt pain; research shows untested agent changes; a gap found in competitors (executed counterexamples in the agent loop).
- **Trade-offs:** Crowded adjacent market; platform vendors own the review surface.
- **Consequences:** Everything below is scoped to this product.
- **Status:** Confirmed (master prompt, Nov 4). *Conflict:* the "Project Knowledge" doc (Nov 3) still says "No idea has been selected"; it is stale. See OQ-B6.

## D-002 Integration surface: a Claude Code plugin
- **Context:** The guard must observe and steer Claude Code (the "frontier model ↔ hook ↔ agentic system ↔ agent feedback" sketch).
- **Options:** Claude Code hooks; an MCP server only; post-hoc CI checks; a wrapper CLI.
- **Decision:** One Claude Code plugin bundling hooks (push: checks on every event), a stdio MCP server (pull: Claude asks for impact data), and skills (slash commands for the developer).
- **Reasoning:** Hooks run whether or not Claude chooses to look, so enforcement doesn't depend on model compliance. Plugins install hooks, MCP and commands together.
- **Status:** Confirmed.

## D-003 When to check: before write, after write, at Stop
- **Options:** post-execution only; pre-write only; all three.
- **Decision:** PreToolUse (fast static check), PostToolUse with `asyncRewake` (behavioral diff in background), Stop (session audit).
- **Reasoning:** Post-only lets Claude build many edits on a bad assumption. Pre-only can't verify behavior and misses edits made through Bash (Edit|Write hooks don't fire for them).
- **Status:** Confirmed.

## D-004 Feedback channel: JSON on stdout, exit 0; async exit 2 to wake Claude
- **Decision:** Hooks print one JSON object and exit 0. `additionalContext` → Claude; `permissionDecision: "deny"` + reason → blocks, reason to Claude; `"ask"` + reason → developer prompt (always paired with `additionalContext` so Claude also knows why); `systemMessage` → developer notice. The async behavioral-diff hook exits 2 so its stderr (the counterexample) wakes Claude.
- **Reasoning:** JSON addresses three audiences separately; exit-2-only can't.
- **Status:** Confirmed.

## D-005 Indexing: four lookup tables, no call graph
- **Context:** Initial team plan was a full AST/call graph of the 20-year codebase.
- **Options:** full call graph; hybrid AST + vector RAG; on-demand LSP/ctags; subgraph slicing via MCP; lookup tables.
- **Decision:** Answer only "who depends on the edited function?" from four tables built ahead of time: (1) names (tree-sitter definitions and calls per file), (2) test coverage (coverage.py per-test contexts), (3) routes and schema (framework introspection, migrations, event schemas), (4) git co-change. Each answer records its source.
- **Reasoning:** The guard only needs answers for the 1–5 functions in the current edit. Full graphs are slow, language-specific, and wrong exactly where legacy code is dangerous (reflection, DI config, string SQL, generated code).
- **Trade-offs:** Name matching over-matches same-named functions and misses dynamic calls.
- **Status:** Confirmed. Subgraph slicing via MCP is kept as the *delivery* mechanism (D-002), not a representation.

## D-006 Full precise call graph as v1
- **Status:** Rejected (slow, false confidence, and Claude Code LSP plugins already provide references).

## D-007 Vector/RAG index for blast radius
- **Status:** Rejected (code similarity is not dependency). Possible later use: finding existing conventions.

## D-008 LLM judge (prompt/agent hook) on every edit
- **Status:** Rejected (30–60 s default timeouts; a model grading a model). An optional prompt hook at Stop only is Deferred.

## D-009 Post-execution-only checking
- **Status:** Rejected (see D-003).

## D-010 Scope: one Python backend service; boundaries are contracts
- **Context:** Enterprise systems include UI, mobile, backend, jobs; the team can't cover everything.
- **Decision:** Guard one backend service (a repo or a subfolder, set by `scope:` in config). Web/mobile/partner clients, the database, queues and third parties are out of scope and protected through contracts: HTTP API (openapi.yaml / routes), DB schema (migrations), event schemas.
- **Reasoning:** Business rules live in the backend; contracts are already written down; service functions can run without a browser.
- **Consequences:** Edits outside `scope` get a warning, not a check.
- **Status:** Confirmed.

## D-011 Index the whole enterprise (UI + backend + jobs)
- **Status:** Rejected (too big for a week; UI code can't be checked by running it).

## D-012 Behavioral diff is the core check; the static index only ranks risk
- **Decision:** The decisive evidence is running old vs. new code. Static and history data decide how risky an edit is and what context Claude gets.
- **Reasoning:** Master prompt: "the LLM proposes; execution decides". An LLM can't fake a counterexample.
- **Status:** Confirmed. (Earlier in the conversation the static graph was the main check; that was superseded.)

## D-013 False-alarm budget: only evidence can interrupt a person
- **Decision:**
  - Declared rule (frozen file) → `deny`.
  - Contract break (route, response field, column, event field, deleted or weakened test) → `ask` the developer.
  - Behavior difference the request didn't mention → wake Claude (async exit 2) + `systemMessage` notice to the developer.
  - Risk signals (many callers, history coupling, no tests reach it) → `additionalContext` only, never a prompt.
  - Targets: ≤ 1 developer prompt per 10 edits; ≤ 3 prompts per session (excess goes to the Stop report); 0 wrong blocks (only declared rules deny); ≤ 1 harmless Claude wake-up per 20 edits.
  - Filters: self-diff (run old code twice; drop inputs where old disagrees with old), intent filter, report each finding once per session; waived findings stay quiet until the code changes.
  - If targets are missed: downgrade signals from `ask` to context, starting with history-only signals. Evidence findings are never downgraded.
- **Reasoning:** A guardrail that blocks good roads gets switched off.
- **Status:** Confirmed (provisional). Targets were chosen, not measured; validated by the backtest (TESTING.md).

## D-014 Demo repositories: billing-api + django-oscar
- **Decision:** (a) **billing-api**, built by the team: small FastAPI + SQLite billing service (~3,000 lines) with openapi.yaml, migrations, tests and five planted legacy traps (banker's rounding, a shared date helper, a nightly job caller, an untested report, a frozen ledger file). Used for the live demo. (b) **django-oscar**, a real open-source Django e-commerce framework with Decimal money logic; its tests can run on SQLite. Used for backtest numbers (replay past commits; plant bugs in pricing code). Fallback: **OpenFisca** (tax and benefit rules as Python formulas).
- **Reasoning:** A live demo must be deterministic; judges need evidence on code the team didn't write.
- **Trade-offs:** The controlled repo may look rigged; answered by the real repo.
- **Status:** Confirmed (provisional), pending feasibility check OQ-B1. FastAPI for billing-api is Proposed.

## D-015 No Anthropic API; run on the user's Claude Code Pro/Max plan
- **Context:** No budget for API usage; users are assumed to have Claude Code on Pro or Max.
- **Decision:** The guard never calls a model. All guard components are local Python. The only model is Claude Code itself on the user's plan. Intent judgments go to the Claude already in the session, with the developer deciding. `claude -p` (plan usage) is used for the guard-on/off comparison.
- **Consequences:** SessionStart warns if `ANTHROPIC_API_KEY` is set. Plan limits (5-hour and weekly windows, shared with claude.ai) constrain evaluation runs.
- **Status:** Confirmed.

## D-016 Calling the Claude API from the guard
- **Status:** Rejected (costs money; no check needs it).

## D-017 Distribution
- **Decision:** During development, `claude --plugin-dir ./legacyguard` (+ `/reload-plugins`). For users, a GitHub repo published as a plugin marketplace (`/plugin marketplace add <org>/legacyguard`, `/plugin install legacyguard@legacyguard`).
- **Status:** Confirmed. The GitHub org/repo name is Unresolved.

## D-018 Human-in-the-loop modes
- **Decision:** `advisory` (never blocks), `guarded` (default; contract break → ask, declared rule → deny), `strict` (high-risk → deny until waived). Per finding: approve/reject at the native prompt, `/legacyguard:waive <id> "<reason>"` (recorded in `waivers.json`), `/legacyguard:pin <id>` (developer-approved regression test), `/legacyguard:mode`. Optional automation: run Claude Code in auto mode; a hook's `"ask"` still forces a prompt.
- **Status:** Confirmed.

## D-019 Shared state: SQLite read by stateless hooks and the MCP server
- **Decision:** Hooks are short-lived processes; they and the MCP server share `.legacyguard/index.db`. No daemon.
- **Status:** Confirmed. Routing hook checks through `mcp_tool` hooks to a warm MCP process is Deferred (and `mcp_tool` hooks don't run at SessionStart launch).

## D-020 Fail open by default
- **Decision:** Leave `onFailure` unset in the demo so a guard bug never freezes Claude; offer `onFailure: "block"` in strict mode (needs Claude Code v2.1.295+).
- **Status:** Proposed (recommended, not explicitly confirmed).

## D-021 How old code is obtained for the behavioral diff
- **Discussed:** (a) PreToolUse saves a snapshot of the pre-edit file; (b) SessionStart checks out the baseline commit with `git worktree` and the runner imports old code from there in a separate subprocess.
- **Status:** Partly unresolved. Mechanism (b) is the proposed runner design. Whether the diff compares against the **session baseline** or the **previous edit** is open (OQ-B3).

## D-022 "Never again" memory
- **Discussed:** pinned counterexamples as regression tests (developer-approved via `/legacyguard:pin`), repository rules file (`frozen:` in config), mined transformation rules (MELT).
- **Status:** Pinned regression tests and the frozen list are in the MVP design (Confirmed). Mined rules are Deferred. The master prompt lists the final storage mix as an open decision (OQ-N2).

## D-023 Product name
- **Status:** Unresolved. "LegacyGuard" / `legacyguard` is a working name used in diagrams and paths.

---

# One-pass build defaults (added 2026-11-05)

Each entry below records a default chosen by the team for the one-pass M0–M8 build. Status for all: **Confirmed (default for one-pass build; revisit after demo)**.

## D-024 Intent labeling (resolves OQ-B2)
- **Decision:** No automatic "requested" labeling in the MVP. Every behavior difference wakes Claude as `Behavior difference — intent unknown`. The developer accepts an intended change with `/legacyguard:waive <id> "<reason>"`.
- **Status:** Confirmed (default for one-pass build; revisit after demo)

## D-025 Comparison point (resolves OQ-B3)
- **Decision:** Always compare against the session baseline (state at session start), never the previous edit. At SessionStart, create a git worktree at HEAD under `.legacyguard/baseline/`, then copy in the session-start contents of any dirty or untracked files in scope, so the baseline equals the working tree at session start.
- **Status:** Confirmed (default for one-pass build; revisit after demo)

## D-026 Target interpreter (resolves OQ-B4)
- **Decision:** Config key `python:`. If absent, auto-detect in order: `.venv`, `venv`, `env` (`bin/python`, or `Scripts\python.exe` on Windows), then `python3`/`python` on PATH.
- **Status:** Confirmed (default for one-pass build; revisit after demo)

## D-027 Product name (resolves OQ-N1; updates D-023)
- **Decision:** Keep "legacyguard".
- **Status:** Confirmed (default for one-pass build; revisit after demo)

## D-028 Pinned tests (resolves OQ-N2; updates D-022)
- **Decision:** Written only on `/legacyguard:pin`, to `tests/legacyguard/test_pinned_<id>.py` in the guarded repo. This replaces the `tests/guard/` location proposed in FR-25.
- **Status:** Confirmed (default for one-pass build; revisit after demo)

## D-029 Side effects (resolves OQ-N3)
- **Decision:** Out of the MVP. Compare return values plus exception type and message only. Document this limit in the report footer.
- **Status:** Confirmed (default for one-pass build; revisit after demo)

## D-030 App discovery (resolves OQ-N4)
- **Decision:** Config key `app:` (`module:attribute`, FastAPI) or `django_settings:` (Django settings module).
- **Status:** Confirmed (default for one-pass build; revisit after demo)

## D-031 MCP library (resolves OQ-N5)
- **Decision:** The official `mcp` Python SDK (FastMCP), stdio transport.
- **Status:** Confirmed (default for one-pass build; revisit after demo)

## D-032 Evaluation harness (resolves OQ-N6)
- **Decision:** Build a custom harness around `claude -p`. Try `claude plugin eval` once and note the result, but do not depend on it.
- **Status:** Confirmed (default for one-pass build; revisit after demo)

## D-033 Evaluation sizes (resolves OQ-N7)
- **Decision:** 10 A/B tasks; replay up to 100 django-oscar commits; plant 10 bugs in pricing/offer code. Report the catch rate with no target.
- **Status:** Confirmed (default for one-pass build; revisit after demo)

## D-034 Frozen files in advisory mode (resolves OQ-N8)
- **Decision:** Frozen files are denied in every mode, including advisory. This overrides the "advisory: declared rule → context only" cell in FR-23.
- **Status:** Confirmed (default for one-pass build; revisit after demo)

## D-035 Baseline worktree lifecycle (resolves OQ-N9)
- **Decision:** At each SessionStart, remove (`git worktree remove --force`) and recreate it.
- **Status:** Confirmed (default for one-pass build; revisit after demo)

## D-036 billing-api stack (resolves OQ-N15)
- **Decision:** FastAPI + SQLite.
- **Status:** Confirmed (default for one-pass build; revisit after demo)

## D-037 Repository layout for the one-pass build
- **Context:** The project folder sits inside an unrelated personal git repository (`Life Lane`). billing-api must also be its own git repository, because the planted co-change history and the baseline worktree need paths such as `billing/fees.py` at the repository root.
- **Decision:** `Hatchathon/` is its own git repository. billing-api's source is tracked at `demo/billing-api-src/`; `demo/build_billing_repo.py` generates `demo/billing-api/` (gitignored) with its planted history. A nested `.git` cannot be tracked by the outer repository without a submodule.
- **Status:** Confirmed (default for one-pass build; revisit after demo)

---

# After the one-pass build

## D-038 Session map: a view of the changed functions' radius, not a call graph
- **Context:** After the build, the team asked for a map or tree showing what changed and its blast radius, as the developer's final reading output. Approved by the team on 2026-11-05 as milestone M9.
- **Options:** terminal text only; a whole-repo graph; a per-session map limited to changed functions and their dependents.
- **Decision:** One self-contained HTML file per session, `.legacyguard/reports/<session>.html`, written at Stop next to the Markdown report, plus `/legacyguard:map` and a text tree in `/legacyguard:impact`. It shows only this session's changed functions and their callers up to 3 hops, from the existing lookup tables. Edges are name matches: an edge is drawn solid only when one test runs both ends, and dashed otherwise. Colors map to the five finding statuses and to whether any test reaches a caller. No score, and never the word "safe".
- **Reasoning:** The data already exists in `index.db` and `session.json`, so this is rendering with no new analysis. A whole-repo graph would reintroduce D-006. Marking guessed edges keeps a static guess from posing as proof (D-005).
- **Trade-offs:** Name matching can show a wrong caller or miss a dynamic one. Scheduled jobs are not indexed, so only API routes are labeled as entry points.
- **Status:** Confirmed (approved for M9)
