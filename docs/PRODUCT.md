# PRODUCT.md — Product Vision

Labels: **Confirmed** = agreed by the team. **Proposed** = suggested, not explicitly agreed. **Rejected** = do not reintroduce. **Unresolved** = see [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

Sources: the team's master prompt ("Master Prompt — Agent Guardrails", Nov 4, 2026), and the architecture conversation of Nov 5, 2026.

## 1. The real-world problem (Confirmed)

Developers using Claude Code, Copilot and Cursor get changes that look done but quietly break something:

- The agent reports "Done. All tests pass." Two days later something unrelated breaks in a file the agent never mentioned.
- A small change touches a shared utility, and half the system behaves differently. That part had no tests.
- The agent can't make a test pass, so it edits the test instead.
- The agent repeats the same mistake next session because it doesn't remember corrections.
- Developers approve 800-line diffs they didn't write because they're tired.
- In legacy systems, nobody fully understands the old code; business rules live only in the code.

The team's framing: the agents are already brilliant programmers. The goal is not a smarter agent but one that **stops driving off cliffs**, turns back when it nearly does, and **never takes that road again**.

### Evidence gathered so far (from the master prompt, Nov 3 research; cite the papers, not this file)

- In 4,882 agent PRs, agents added no test changes 50.4% of the time; existing tests executed only 61.5% (Java) and 27.0% (Python) of agent-changed lines (Dipongkor et al., arXiv:2607.18057).
- A static code–test map (TDAD) cut agent test-level regressions from 6.08% to 1.82% on 100 SWE-bench Verified tasks (arXiv:2603.17973).
- Maintainers would not merge roughly half of SWE-bench-passing agent PRs (METR, Mar 2026).
- Agents score over 80% on isolated tasks but at most 38% when changes accumulate on one codebase (EvoClaw, ICML 2026).
- **Not found:** the dollar cost of agent regressions, or agent vs. human regression rates on matched tasks. Do not claim either.

## 2. Why existing solutions are insufficient (Confirmed, from master prompt research)

| Category | Examples | Gap |
| --- | --- | --- |
| Impact graphs | GitNexus (noncommercial license), Greptile, CodeRabbit, Qodo | Show what *might* break; don't execute old vs. new |
| Test selection | TDAD, CloudBees Smart Tests | Only as good as existing tests; most agent-changed lines are never executed |
| Maintainability gates | CodeScene, SonarQube | Heuristics, not behavior |
| LLM review | Claude Code Review, Copilot | A model grading a model; no executed evidence |
| Replay tools | Keploy, Meticulous | Need recorded production traffic or browser sessions |
| LSP navigation for agents | Claude Code LSP plugins (e.g. zircote/lsp-tools enforces LSP-first impact analysis) | Gives Claude references; doesn't enforce or prove behavior |

**Our gap:** no product found runs the old and new versions of changed functions in-repo, inside the agent loop, and feeds counterexamples back to the agent. Anything that is only "better prompts plus a graph" will be absorbed by Anthropic, GitHub or Qodo.

## 3. Proposed solution (Confirmed)

A Claude Code plugin that guards one Python backend service:

1. **Before each write**, a fast static check catches contract breaks (API, DB schema, event schema), frozen files, and risky blast radius.
2. **After each write**, a background **behavioral diff** runs old vs. new code on the same inputs. A difference the request didn't mention wakes Claude with a replayable counterexample, so Claude revises before a human sees the diff.
3. **When Claude tries to finish**, a session audit checks the whole diff (including edits made through shell commands), test integrity and contracts, and writes a report where every finding has one honest status.
4. The developer stays in the same terminal: rare permission prompts, waivers, and pinning a counterexample as a regression test.

### The guiding metaphor ("Road Above the Clouds")

The team's interactive (claude.ai artifact, link in the master prompt; its content is not reproduced here) is the product's picture:

| Metaphor | Product |
| --- | --- |
| Car | One agent task or edit session |
| Junction | A point where the agent commits: an edit, a tool call, a stop |
| Road ending in sky | A change that breaks behavior, a contract, a test's meaning, or a layering rule |
| Guardrail | A deterministic check that executes and produces evidence |
| Turned back | Claude receives a counterexample and revises before a human sees the diff |
| Never takes that road again | The correction becomes a durable, machine-checked rule (e.g. a pinned regression test) |
| Fell | A regression reaches review, merge or production |
| Two destinations, a bypass | Several valid implementations exist; the guard must not over-constrain |
| Clicking an arrow | Developer overrides, accepts an intended change, or steers |
| Arrived / Turned back / Fell | The evaluation metrics |

## 4. Intended users (Confirmed)

- **Hackathon wedge:** developers and small teams using Claude Code heavily on Python backends. They already have Claude Code on a **Pro or Max plan**; the guard must cost nothing extra.
- **Long-term company:** organizations modernizing legacy systems, where the old system is the most trusted oracle.

## 5. Key workflows (Confirmed)

1. **Set up once:** install the plugin, add `.legacyguard/config.yaml` to the backend repo, run `/legacyguard:index`.
2. **Normal session:** the developer asks Claude for a change. Low-risk edits flow with no interruption. Claude gets blast-radius context before planning.
3. **Turned back:** Claude's edit changes behavior the request didn't mention. The guard wakes Claude with the counterexample; Claude fixes it; the guard re-verifies.
4. **Human decision:** a contract break (route, response field, column, event field, deleted/weakened test) triggers a permission prompt. The developer approves, rejects or waives.
5. **Finish:** the Stop audit writes a report. The developer may pin a counterexample as a regression test.

## 6. Core value proposition (Confirmed)

Executed evidence, inside the agent loop, before review: the agent gets a concrete counterexample it can act on, and the developer gets a 10-second report that says what was checked and what wasn't, without leaving Claude Code.

## 7. MVP boundaries (Confirmed unless marked)

In the MVP:
- One Python backend service per guarded repo.
- Claude Code only (not Copilot or Cursor).
- Hooks: SessionStart, UserPromptSubmit, PreToolUse, PostToolUse (async), Stop.
- Behavioral diff for functions callable in isolation; everything else reported as **Untested**.
- Contract checks for HTTP API, DB migrations and event schemas.
- Test-integrity check (deleted or weakened tests).
- Modes advisory / guarded / strict; waive and pin commands.
- Demo on a controlled repo (billing-api) plus a backtest on a real repo (django-oscar).

Not in the MVP (deferred):
- Precise references through a Python language server (only if name matches prove too noisy).
- Mined transformation rules (MELT-style) for "never again".
- Optional LLM intent label at Stop via a prompt hook.
- Mocking external services so more functions become runnable.
- Status line integration (optional polish).

## 8. Long-term vision (Proposed, from master prompt)

**Legacy mode:** business rules extracted from legacy code (cf. the COBOL/PL/I requirements-extraction paper in the project files) become invariants the new code must preserve. The same engine becomes a **migration verifier** for modernization programs. Later: more languages, more agents, team-wide memory of "never again" rules.

## 9. Explicit non-goals (Confirmed)

- Not a smarter coding agent; not a code generator.
- Not a reviewer that grades with an LLM.
- Not a whole-enterprise indexer (UI, mobile, other services are out of scope; they are protected through contracts).
- Not a "health score".
- Not an auto-approver, merger or deployer.
- Not a product that calls the Anthropic API or needs paid API credits.
- Does not guarantee safety; it reports evidence.

## 10. Hackathon context (Confirmed)

- Expo: one 2.5-minute pitch at the table; top two per track advance. Finale: 3-minute stage pitch.
- Rubric (1–10 each, equal weight): Problem Identification, Solution Innovation, Technical Execution, User Experience & Design, Impact Potential, Team.
- Plan to earn Technical Execution with a live run: guard on vs. off, same agent, same tasks, real Arrived / Turned back / Fell counts.
- **Unresolved:** whether the pitch leads with everyday agent safety or legacy modernization; team roles; product name.
