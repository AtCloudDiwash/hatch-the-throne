# TECH_STACK.md — Technology Decisions

Labels: **Confirmed**, **Proposed**, **Rejected**, **Unresolved**.

## 1. Confirmed technologies

### Claude Code (CLI) on a Pro or Max plan
- **Purpose:** The coding agent being guarded; the only model in the system.
- **Why:** Target users already have it; no extra cost (D-015). The team uses Claude Max.
- **Used by:** Everything; hooks and the MCP server are started by Claude Code.
- **Constraints:**
  - Usage counts against plan limits (5-hour and weekly windows, shared with claude.ai).
  - `claude -p` and the Agent SDK can use the plan; usage counts against the same limits.
  - If `ANTHROPIC_API_KEY` is set, Claude Code bills that key per token. Never set it.
  - `/usage` shows usage attributed to plugins and MCP servers (useful to show the guard's overhead).
  - Pin a minimum Claude Code version before the demo (exact version Unresolved). Known version floors: `onFailure` needs v2.1.295+; `asyncRewake` is recent.
- **Alternatives:** Copilot, Cursor (Future, not MVP).

### Claude Code hooks
- **Purpose:** Push checks at SessionStart, UserPromptSubmit, PreToolUse (`Edit|Write`), PostToolUse (`Edit|Write`, async), Stop.
- **Key facts relied on:**
  - Command hooks get JSON on stdin; output one JSON object on stdout with exit 0.
  - PreToolUse `permissionDecision`: `allow` | `deny` | `ask` | `defer` (`defer` only in `-p`; not used). Precedence deny > defer > ask > allow.
  - `ask` reason is shown to the user; `deny` reason is shown to Claude.
  - `additionalContext` is delivered as a system reminder; capped at 10,000 chars.
  - Exit 2 on PostToolUse shows stderr to Claude (tool already ran).
  - `asyncRewake: true` runs a command hook in the background and wakes Claude on exit 2 with its stderr.
  - Stop: `decision: "block"` + `reason` keeps Claude working; `stop_hook_active` prevents loops.
  - Default timeouts: command 600 s; UserPromptSubmit 30 s; prompt hooks 30 s; agent hooks 60 s.
  - `type: "mcp_tool"` hooks are skipped at SessionStart launch.
  - PostToolUse `Edit|Write` does not fire when Bash rewrites a file.
  - A hook's `ask` forces a prompt even in auto mode; in `-p` runs an unanswerable prompt is denied and Claude reads the reason.
  - `--settings '{"disableAllHooks": true}'` disables hooks for one run.
  - File paths in `tool_input` are absolute; Windows uses backslashes.
- **Alternatives considered:** exit-2-only signaling (Rejected as primary channel, D-004); prompt/agent hooks per edit (Rejected, D-008).

### Claude Code plugin system
- **Purpose:** Package hooks, MCP server and skills (D-002, D-017).
- **Details:** `.claude-plugin/plugin.json`; `hooks/hooks.json`; `.mcp.json`; `skills/<name>/SKILL.md` invoked as `/legacyguard:<name>`; `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_DATA}` placeholders; `claude plugin validate`; `claude --plugin-dir`; `/reload-plugins`; marketplace install from a GitHub repo.

### MCP (Model Context Protocol), stdio server
- **Purpose:** Pull queries from Claude (`impact`, `contract`, `diff_report`).
- **Constraint:** Tool names scoped `mcp__plugin_legacyguard_<server>__<tool>`.
- **Library:** Unresolved (OQ-N5); the team only agreed "stdio, Python".

### Python 3.10+
- **Purpose:** Language of every guard component; also the MVP target language.
- **Why:** Master prompt default; behavioral diff needs callable functions; tree-sitter, Hypothesis and coverage.py exist.

### SQLite
- **Purpose:** `.legacyguard/index.db`, shared by stateless hooks and the MCP server (D-019).
- **Why:** Zero setup, single file, fast enough for per-edit lookups.

### tree-sitter (Python grammar)
- **Purpose:** Per-file parsing for the names table and for before/after symbol diffs in PreToolUse.
- **Why:** Fast, incremental-friendly, works on broken code.
- **Alternatives:** full call graph (Rejected, D-006); SCIP indexers (not adopted); language server lookups (Deferred).

### git
- **Purpose:** Co-change history; baseline commit; `git worktree` for old code; Stop-time diff.

### coverage.py dynamic contexts
- **Purpose:** Test → function map (`[run] dynamic_context = test_function`).
- **Why:** Observed execution, not a guess.

### Hypothesis
- **Purpose:** Generate inputs for the behavioral diff alongside test-harvested inputs.

### PyYAML (or equivalent)
- **Purpose:** Read `config.yaml`. Specific library is an implementation detail (Proposed).

## 2. Demo and evaluation

| Item | Purpose | Status |
| --- | --- | --- |
| billing-api (built by team) | Live demo repo with five planted traps | Confirmed (provisional) |
| FastAPI + SQLite for billing-api | Demo app framework and DB | Proposed |
| openapi.yaml | HTTP contract for billing-api | Confirmed (design) |
| django-oscar | Real-repo backtest (BSD-licensed Django e-commerce; tests can run on SQLite with `--sqlite`) | Confirmed (provisional), feasibility check pending |
| OpenFisca | Fallback backtest repo (tax/benefit rules as Python formulas) | Proposed fallback |
| `claude -p` | Guard on/off comparison on team plans | Confirmed |
| `claude plugin eval` | Built-in with/without-plugin scoring; may replace the custom A/B harness | Unresolved (OQ-N6) |
| pytest | Test runner for the guard and for billing-api | Proposed (django-oscar uses pytest) |

## 3. Explicitly not used

| Technology | Reason | Status |
| --- | --- | --- |
| Anthropic API / API key | Costs money; no check needs a model | Rejected (D-016) |
| Vector database / embeddings | Similarity is not dependency | Rejected (D-007) |
| Full call-graph builders | Slow, wrong on dynamic code | Rejected (D-006) |
| Prompt/agent hooks per edit | Too slow; model grading model | Rejected (D-008) |
| Long-running daemon | Hooks are stateless; SQLite is the shared state | Not adopted (D-019) |

## 4. Future candidates (not agreed)

- Python language server (pyright or Jedi) for precise references on edited functions only, if name matches are too noisy.
- MELT-style mined transformation rules for "never again" (paper in project files).
- APIDiff-style breaking-change taxonomy (paper in project files; Java tool, used as inspiration only).
- DockerizeMe-style environment inference (paper in project files) to make more functions runnable. Not discussed in this conversation beyond the file list.
