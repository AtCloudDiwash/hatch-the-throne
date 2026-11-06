# REQUIREMENTS.md — Functional Specifications

IDs: `FR-xx` functional, `NFR-xx` non-functional. Labels: **Confirmed**, **Proposed**, **Unresolved**. Priority: **MVP** or **Future**.
Architecture: [ARCHITECTURE.md](ARCHITECTURE.md). Decisions: [DECISIONS.md](DECISIONS.md). Open items: [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

Terms:
- **Guarded repo**: the backend service repo the developer opens Claude Code in.
- **Scope**: the folder named by `scope:` in config.
- **Finding**: one result of a check, with an ID (`LG-<n>`), a status, a source, and evidence.
- **Finding statuses** (exactly one each): `Verified pass`, `Confirmed failure`, `Behavior difference — intent unknown`, `Potential risk (static only)`, `Untested`.
- **Sources**: `names`, `tests`, `routes`, `schema`, `history`, `diff`, `rule`.

---

## A. Packaging and setup

### FR-01 Plugin package — Confirmed — MVP
- **Problem:** Hooks, MCP server and commands must install together.
- **Behavior:** A directory `legacyguard/` with `.claude-plugin/plugin.json`, `hooks/hooks.json`, `.mcp.json`, `skills/`, scripts. Loads with `claude --plugin-dir ./legacyguard`; distributable through a GitHub marketplace.
- **Edge cases:** Only `plugin.json` inside `.claude-plugin/`; hook commands use `${CLAUDE_PLUGIN_ROOT}` in exec form.
- **Acceptance:** `claude plugin validate ./legacyguard` passes; `/plugin` lists the plugin with its hooks, MCP server and skills; `/mcp` shows the server connected.

### FR-02 Configuration file — Confirmed — MVP
- **Input:** `.legacyguard/config.yaml` in the guarded repo:
  ```yaml
  scope: billing-api/
  language: python
  mode: guarded            # advisory | guarded | strict
  contracts:
    http: openapi.yaml
    db: migrations/
    messages: schemas/events/
  frozen:
    - billing-api/legacy/ledger_v1.py
  behavioral_diff:
    network: blocked
    max_inputs: 500
    timeout_s: 60
    self_diff: true
  alarm_budget:
    max_prompts_per_session: 3
    may_interrupt: [frozen, contract_break, behavior_difference]
    context_only: [many_callers, history_coupling, untested]
  ```
- **Behavior:** Every hook reads it on each call (mode changes apply immediately). Missing file → the guard does nothing except a one-time `systemMessage` explaining how to set up.
- **Edge cases:** Invalid YAML → `systemMessage` with the parse error; guard stays inactive (fail open). Path to the target project's Python interpreter is **Unresolved** (OQ-B4).
- **Acceptance:** Changing `mode` mid-session changes the next decision; invalid config never blocks Claude.

### FR-03 Environment bootstrap — Confirmed — MVP
- **Behavior:** On first SessionStart, create the guard's own virtual environment in `${CLAUDE_PLUGIN_DATA}` and install tree-sitter (+ Python grammar), Hypothesis, coverage, PyYAML (and the MCP library, OQ-N5). Requires Python 3.10+ and git on the machine.
- **Edge cases:** No network for install → `systemMessage` with the manual command; guard inactive.
- **Acceptance:** A clean machine with Python and git gets a working guard after one session start.

## B. Index

### FR-04 Names table — Confirmed — MVP
- **Behavior:** tree-sitter parses each `.py` file in scope independently. Store each definition (qualified name, kind, file, line span, signature text and hash, decorators) and each call site (calling function, called name).
- **Edge cases:** Same-named functions are all returned, marked `source: names`; dynamic calls (`getattr`, string dispatch) are missed by design.
- **Acceptance:** For billing-api, `impact("compute_late_fee")` lists every direct caller in the source.

### FR-05 Test coverage map — Confirmed — MVP
- **Behavior:** Run the test suite once with coverage.py dynamic contexts (`dynamic_context = test_function`). Map each test to the functions whose lines it executed.
- **Edge cases:** Suite fails to run → map empty, status recorded; functions with no covering test → `Untested` findings.
- **Acceptance:** For a function covered by N tests, the map returns those N tests.

### FR-06 Routes and schema — Confirmed — MVP
- **Behavior:** List routes from the framework itself (FastAPI app routes / Django URL resolver), map route → handler function, read migrations and event schemas named in config, read the HTTP contract file (openapi.yaml).
- **Edge cases:** Unusually registered routes may be missed; the framework app import path is **Unresolved** per repo (OQ-N4).
- **Acceptance:** Every route in billing-api's openapi.yaml maps to a handler.

### FR-07 Git history — Confirmed (co-change) / Proposed (churn, bug-fix density) — MVP
- **Behavior:** Mine `git log --name-only` for file co-change pairs with support and confidence (e.g. "changes with `db/rates.sql` in 82% of commits").
- **Acceptance:** Planted co-change pairs in billing-api's history are reported.

### FR-08 Incremental re-index — Confirmed — MVP
- **Behavior:** Re-parse only files whose git blob SHA changed since the last index; triggered at SessionStart and by `/legacyguard:index`.
- **Acceptance:** Re-index after a one-file change touches one file.

### FR-09 Impact query — Confirmed — MVP
- **Behavior:** Given function(s), return: callers (up to 3 hops), public routes reaching them, tests executing them, co-changed files, frozen/contract membership. Every item carries its source(s). Shared by hooks and the MCP server.
- **Output example:**
  ```text
  callers  settle_invoice() [names,tests]  close_month() [names, history 71%]  aging_bucket() [names] no test reaches it
  routes   POST /invoices/{id}/settle [routes]
  tests    6 [tests]
  co-change db/rates.sql [history 82%]
  ```
- **Acceptance:** Output for one function stays under ~1,500 characters (truncate with a count).

## C. Hooks

### FR-10 SessionStart hook — Confirmed — MVP
- **Behavior:** (1) bootstrap check (FR-03); (2) incremental re-index (FR-08); (3) record the baseline commit and create the baseline `git worktree` under `.legacyguard/baseline/`; (4) reset session state (`session.json`); (5) warn via `systemMessage` if `ANTHROPIC_API_KEY` is set; (6) add a short summary to Claude's context: scope, mode, contract files, frozen files, available guard tools.
- **Constraints:** Must be `type: "command"` (MCP-tool hooks are skipped at launch).
- **Edge cases:** Dirty working tree at start → baseline is HEAD plus a record of dirty files (OQ-B3); not a git repo → guard inactive with a notice.
- **Acceptance:** After start, `.legacyguard/baseline/` exists at the baseline commit and Claude's context contains the summary.

### FR-11 UserPromptSubmit hook — Confirmed — MVP
- **Behavior:** Find indexed files/functions named in the prompt; add their impact (FR-09) as `additionalContext`. Store the prompt text in session state for intent handling (FR-16).
- **Constraints:** Fast (target < 2 s; default timeout is 30 s). Never modify or block the prompt.
- **Acceptance:** A prompt mentioning `billing/fees.py` gives Claude the callers, routes and tests of functions in that file.

### FR-12 PreToolUse hook on `Edit|Write` — Confirmed — MVP
- **Input:** `tool_input.file_path`, and `old_string`/`new_string`/`replace_all` (Edit) or `content` (Write).
- **Behavior:**
  1. Outside scope → allow + `systemMessage` "outside guarded scope".
  2. Frozen file → `deny` + reason.
  3. **Virtual apply:** read the current file, apply the edit in memory, parse before/after with tree-sitter, diff symbols (signature change, deletion, rename, visibility change).
  4. Contract check: route removed, parameter renamed, response field dropped (HTTP contract); column dropped/renamed in a new migration; event field removed/retyped; test deleted or assertions removed → **contract break** → `ask` (within the prompt budget, FR-20) + `additionalContext`.
  5. Otherwise allow; add impact context only when risk signals exist.
- **Output:** one JSON object, `hookSpecificOutput.permissionDecision` ∈ {allow, ask, deny}, `permissionDecisionReason`, `additionalContext`.
- **Constraints:** ~1 s; paths normalized for Windows separators.
- **Edge cases:** `old_string` not found or not unique (without `replace_all`) → allow, no finding (Claude's tool will fail itself); unparsable new code → allow + context "new code does not parse".
- **Acceptance:** Dropping a response field in billing-api produces an `ask` prompt labeled `[plugin:legacyguard]`; editing the frozen ledger file is denied.

### FR-13 PreToolUse hook on `Bash` (file-mutating commands) — Proposed — Future
- **Behavior:** Flag commands like `sed -i`, redirects, `mv`, `rm`, `git checkout --` on files in scope.
- **Note:** The MVP relies on the Stop audit (FR-18) to catch Bash edits.

### FR-14 Behavioral diff runner — Confirmed — MVP
- **Input:** changed functions; baseline worktree; working tree; target project's Python.
- **Behavior:**
  1. Inputs: arguments harvested from existing tests that execute the function + Hypothesis-generated values from type hints/defaults; capped at `max_inputs`.
  2. Spawn two subprocesses of the target project's Python: one imports the baseline worktree, one imports the working tree. Both receive the same serialized inputs.
  3. Network blocked: a startup file makes socket connections raise.
  4. Self-diff: run old code twice per input; drop inputs where old disagrees with old (nondeterministic).
  5. Compare return values and exception types/messages. (Side-effect comparison: Unresolved, OQ-N3.)
  6. Functions that can't be called in isolation (DB, network, global state) → `Untested` with the reason.
- **Output:** per function: inputs tried, differing inputs (each replayable: function, args, before, after), status.
- **Constraints:** `timeout_s` per run; deterministic serialization.
- **Acceptance:** On billing-api, replacing `quantize(CENT, ROUND_HALF_UP)` with `round(x, 2)` yields counterexample `compute_late_fee(balance=Decimal("40.20"), rate=Decimal("0.025"))` → before `1.01`, after `1.00` (verified in Python).

### FR-15 PostToolUse hook on `Edit|Write` (async) — Confirmed — MVP
- **Behavior:** Configured with `asyncRewake: true`. Runs FR-14 on functions changed by the edit. On a difference not covered by intent (FR-16) → exit 2, stderr = compact counterexample (≤ ~1,500 chars), and record finding `Behavior difference — intent unknown`. On no difference → exit 0, record `Verified pass (N inputs)` in session state.
- **Note:** The map's step 6 says success is reported via `additionalContext`; whether a background hook's stdout reaches Claude is unverified (OQ-B5). Until verified, success is recorded in session state and shown at Stop and in `/legacyguard:status`.
- **Acceptance:** In the demo scenario Claude is woken with the counterexample and its next edit restores the original rounding; re-check records Verified pass.

### FR-16 Intent handling — Confirmed (principle) / Unresolved (mechanism) — MVP
- **Behavior:** Every difference starts as `Behavior difference — intent unknown`. Claude, already in the session, reads the counterexample and either reverts or explains; the developer has the final say (approve via waive with reason). The model never grades its own output; execution produces the evidence.
- **Unresolved:** how a difference is automatically labeled "requested" when the prompt asked for it (OQ-B2).
- **Acceptance:** No automated path marks a difference "requested" without either a developer action or an agreed mechanism.

### FR-17 Test-integrity check — Confirmed — MVP
- **Behavior:** Flag deleted tests, removed/weakened assertions, and tests edited in the same session as the code they test. At PreToolUse on test files → contract break → `ask`. At Stop → included in the report.
- **Acceptance:** Deleting an assertion from a billing-api test produces an `ask` and a Stop-report entry.

### FR-18 Stop hook (session audit) — Confirmed — MVP
- **Behavior:** Diff the working tree against the baseline (catches Bash edits); run contract checks and test integrity on the whole diff; run the behavioral diff for changed functions not yet checked; list callers of changed functions that weren't updated when the signature changed. If unresolved high-risk evidence remains and `stop_hook_active` is false → `decision: "block"` + reason (Claude continues). If `stop_hook_active` is true → allow stop, write report, `systemMessage` summary.
- **Acceptance:** A Bash-made change to a contract file is reported at Stop; the hook never blocks twice in a row.

## D. Findings, budget and developer control

### FR-19 Session report — Confirmed — MVP
- **Behavior:** Write `.legacyguard/reports/<session>.md` and show a `systemMessage` summary: one line per finding with status, subject and evidence; prompts used (`x of 3`); Claude wake-ups; pin suggestions.
- **Acceptance:** Readable in 10 seconds; every non-pass finding has a replayable input or a stated reason it's untested.

### FR-20 Findings ledger and alarm budget — Confirmed (provisional targets) — MVP
- **Behavior:** `session.json` stores findings (`LG-<n>`), sources, statuses, prompt count, wake-up count. Enforces D-013: only `frozen`, `contract_break`, `behavior_difference` may interrupt; max prompts per session (beyond → Stop report); each finding reported once per session; waived findings silent until the code changes.
- **Acceptance:** A 4th contract break in one session produces no prompt and appears in the report.

### FR-21 MCP server — Confirmed (server) / Proposed (exact tools) — MVP
- **Behavior:** stdio server bundled in the plugin. Tools: `impact(symbol, depth)`, `contract(path)`, `diff_report(function)`. Earlier proposals also included `cochange(file)`, `risk(file)`, `rules(path)`.
- **Constraint:** Plugin tools are named `mcp__plugin_legacyguard_<server>__<tool>`.
- **Acceptance:** Claude can call `impact` and get FR-09 output.

### FR-22 Skills (slash commands) — Confirmed — MVP
- `/legacyguard:index` — build/refresh the index.
- `/legacyguard:status` — current findings, mode, prompts used.
- `/legacyguard:impact <symbol>` — FR-09 output.
- `/legacyguard:waive <id> "<reason>"` — FR-24.
- `/legacyguard:pin <id>` — FR-25.
- `/legacyguard:mode <advisory|guarded|strict>` — FR-23.

### FR-23 Modes — Confirmed — MVP
| Mode | Contract break / high risk | Declared rule |
| --- | --- | --- |
| advisory | context only | context only |
| guarded (default) | `ask` | `deny` |
| strict | `deny` until waived | `deny` |
- Optional automation: Claude Code auto mode; the guard's `ask` still forces a prompt.

### FR-24 Waivers — Confirmed — MVP
- **Behavior:** Record `{id, reason, file, symbol, code hash, date}` in `.legacyguard/waivers.json` (committable audit trail). A waiver stops repeats until the code hash changes.

### FR-25 Pin a counterexample — Confirmed (principle) / Proposed (details) — MVP
- **Behavior:** On developer command only, generate a regression test that replays the counterexample against current expected behavior. Proposed location: `tests/guard/test_pinned_<id>.py`.
- **Unresolved:** where pinned tests live and their format in each repo (OQ-N2).

### FR-26 Status line — Proposed — Future
- Script reading `session.json` (e.g. `guard: 2 high · 1 waived`); configured once in user settings.

## E. Demo and evaluation

### FR-27 billing-api demo repo — Confirmed (provisional) — MVP
- FastAPI (Proposed) + SQLite, ~3,000 lines, openapi.yaml, migrations, test suite, git history with planted co-change. Five planted traps: banker's rounding, a shared date helper, a nightly job caller, an untested report, a frozen ledger file. Same task set run with the guard on and off.

### FR-28 Backtest harness — Confirmed — MVP
- `legacyguard backtest` replays real past commits of django-oscar (presumed good) to measure prompt and wake-up rates, and plants bugs in pricing/offer code (known bad) to measure catches. No Claude involved.

### FR-29 Guard on/off comparison — Confirmed — MVP
- Same tasks via `claude -p "$TASK" --plugin-dir ./legacyguard` vs. `claude -p "$TASK"`, on the team's plans. Count **Arrived**, **Turned back**, **Fell** (definitions in TESTING.md). Alternative to evaluate: `claude plugin eval` (OQ-N6).

### FR-30 Session map — Confirmed — Post-MVP (M9)
- **Problem:** The Markdown report lists findings, but a developer can't see what a change reaches.
- **Behavior:** At Stop, and on `/legacyguard:map`, write `.legacyguard/reports/<session>.html`: one self-contained file, no network. It shows each function changed this session with its finding status, its callers up to 3 hops (FR-09), which callers no test reaches, and API routes that reach them. Clicking a node shows its evidence or the reason it is untested, and highlights what is connected. `/legacyguard:impact` also prints the same radius as a text tree.
- **Constraints:** Only changed functions and their radius, never the whole repo (D-006, D-038). An edge is solid only when one test runs both ends; otherwise dashed, as a name match. Colors mean the five statuses or test reach, nothing else. A failure to build the map never blocks Stop or the Markdown report.
- **Acceptance:** After the rounding edit on billing-api, the map shows `compute_late_fee` as a behavior difference with its counterexample, `projected_fee` and `aging_bucket` as dependents no test reaches, and the settle route.

### FR-31 Session story — Confirmed — Post-MVP (M11)
- **Problem:** The findings table is precise but a developer first wants to know what happened.
- **Behavior:** The session report and the session map start with "What happened": what was asked (the stored prompts), what broke (each behavior difference with one example call, before and after), what fixed it (a revision followed by a matching re-run), what was checked, what could not be checked and why, what the developer was asked, and what still needs a decision.
- **Constraints:** Built only from the ledger; no model call. Every line corresponds to a finding. Plain sentences; never "safe".
- **Acceptance:** After the rounding edit and its revert on billing-api, the story reads: asked, broke (with the 40.20 example), fixed (with the re-run count).

### FR-32 First-use setup per repo — Confirmed — Post-MVP (M13)
- **Problem:** A developer had to write `.legacyguard/config.yaml` by hand and run an index command before the guard did anything.
- **Behavior:** At SessionStart in a git repo with at least three tracked Python files and no config, the guard writes `.legacyguard/config.yaml` from what the repo states: `src/` layout, the Django settings module named in the pytest config (else `manage.py`), an `openapi` file. It then starts as usual (baseline, index). The developer gets one notice saying what it watches, and whether a `.venv` was found.
- **Constraints:** An existing config is never overwritten. Any other folder gets no file and no message. `enabled: false` in the config keeps the guard off and quiet in that repo. Writes stay under `.legacyguard/`.
- **Acceptance:** A fresh Python git repo with no guard files: one `claude` session produces a config, an index, and a checked finding for an edit.

### FR-33 Finds a new enough Python — Confirmed — Post-MVP (M13)
- **Problem:** A Mac's `python3` is 3.9 and the guard's libraries need 3.10. Setup failed with a pip error.
- **Behavior:** When the `python3` that starts a hook is older than 3.10, the guard looks for a 3.10+ interpreter already on the machine (PATH and the usual install folders) and builds its environment with that. If there is none, the notice says so in plain words.
- **Acceptance:** Started by Python 3.9 with a 3.12 installed, the guard's environment is 3.12 and a breaking edit is reported.

### FR-34 One-file install — Confirmed — Post-MVP (M13)
- **Problem:** Using the guard meant copying a folder and starting Claude with `--plugin-dir` from the right place every time.
- **Behavior:** `tools/build_package.py` builds `dist/legacyguard.zip`. Its `install.sh` copies the plugin to `~/.legacyguard/package` and registers it through Claude Code's own plugin installer, so the guard loads in every session. Running it again updates.
- **Constraints:** No Docker, no API key, nothing downloaded besides the guard's Python libraries on first use.
- **Acceptance:** In an empty Claude config, `sh install.sh` ends with the plugin listed as installed and enabled.

---

## Non-functional requirements

| ID | Requirement | Status |
| --- | --- | --- |
| NFR-01 | Zero Anthropic API usage; works on Claude Code Pro/Max login only | Confirmed |
| NFR-02 | All guard computation local; no data leaves the machine | Confirmed |
| NFR-03 | PreToolUse ≤ ~1 s; UserPromptSubmit target < 2 s | Confirmed |
| NFR-04 | Each `additionalContext` ≤ ~1,500 chars (hard cap 10,000) | Confirmed |
| NFR-05 | Behavioral diff never makes network calls | Confirmed |
| NFR-06 | Fail open: a guard error never blocks Claude in the demo | Proposed |
| NFR-07 | Alarm budget targets (D-013) | Confirmed (provisional) |
| NFR-08 | Context written as factual statements, not imperative system commands | Confirmed |
| NFR-09 | Works on macOS, Linux and Windows (path normalization) | Confirmed for paths; Windows testing Unresolved |
| NFR-10 | Pin a minimum Claude Code version (asyncRewake, onFailure are recent) | Confirmed; exact version Unresolved |
| NFR-11 | Guard writes only under `.legacyguard/` (except developer-approved pins) | Confirmed |
