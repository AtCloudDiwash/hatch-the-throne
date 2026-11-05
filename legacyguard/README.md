# legacyguard

A Claude Code plugin that guards one Python backend service. Before a write it checks contracts, test integrity and frozen files. After a write it runs the old and new versions of changed functions on the same inputs and gives Claude any counterexample. At Stop it audits the whole session and writes a report.

It makes no model calls and needs no API key. It runs on your Claude Code plan. Tested on Claude Code v2.1.318, which is the pinned minimum.

## Install

```bash
claude --plugin-dir ./legacyguard                    # development
/plugin marketplace add <owner>/<repo>               # from a GitHub marketplace
/plugin install legacyguard --marketplace <owner>/<repo>
```

## Set up a repo

Add `.legacyguard/config.yaml`, then run `/legacyguard:index` once.

```yaml
scope: ./
mode: guarded            # advisory | guarded | strict
app: billing.api.app:app # or django_settings: myproject.settings
contracts:
  http: openapi.yaml
  db: migrations/
  messages: schemas/events/
frozen:
  - legacy/ledger_v1.py
```

The first session start builds the guard's own virtual environment. Optional keys: `python:` (target interpreter, otherwise `.venv`, `venv`, `env`, then PATH) and `source_roots:` (folders to add to the import path, such as `src`).

## Commands

| Command | Who | What |
| --- | --- | --- |
| `/legacyguard:index` | Developer | Build the index and run the tests once |
| `/legacyguard:status` | Anyone | Findings, mode, prompts used |
| `/legacyguard:impact <symbol>` | Anyone | Callers, routes, tests, co-changed files, and a tree of callers |
| `/legacyguard:map` | Developer | Open the session map: what changed, what depends on it, what was checked |
| `/legacyguard:waive <id> "<reason>"` | Developer | Accept a finding until the code changes |
| `/legacyguard:pin <id>` | Developer | Write a regression test from a counterexample |
| `/legacyguard:mode <mode>` | Developer | advisory, guarded or strict |

## Session report

When Claude stops, the guard writes `.legacyguard/reports/<session>.md`. It opens with "What happened": what you asked, what broke with one example, what fixed it, and what could not be checked. A findings table follows.

## Session map

When Claude stops, the guard writes `.legacyguard/reports/<session>.html` next to the Markdown report. It is one offline file. It shows each function changed this session with its status, the functions that call it up to three steps away, which of those no test reaches, and the API routes that lead to them. Click a function for its counterexample or the reason it is untested.

Edges come from matching names. A solid edge means one test runs both functions; a dashed edge is a name match only.

## Limits

- Python only. One service per repo.
- The diff compares return values and exceptions, not side effects.
- Functions that need a database, the network, or objects it can't build are reported `Untested`.
- A `Verified pass` means no difference on the inputs tried.
- Edits made through shell commands are seen only at Stop.
- The map labels API routes as entry points. Scheduled jobs are not indexed, so they appear as ordinary callers.
