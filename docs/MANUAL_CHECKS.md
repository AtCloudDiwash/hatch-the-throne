# MANUAL_CHECKS.md: steps that need a person at an interactive terminal

These could not be verified with `claude -p`. Each lists what to type and what to look for.

## MC-1 The `ask` prompt label (FR-12, E2E-2)

1. `python3 demo/build_billing_repo.py`
2. `cd demo/billing-api && claude --plugin-dir ../../legacyguard`
3. Type: `Remove the "currency" field from the invoice response in billing/api/invoices.py and from openapi.yaml.`
4. Look for: a permission prompt whose text includes `[plugin:legacyguard]` and names the dropped field.
5. Choose **No**. Look for: Claude explains the contract break, because it also received `additionalContext`.

## MC-2 Plugin panels (FR-01, T1.1)

1. In a `claude --plugin-dir ./legacyguard` session, type `/plugin`. Look for: legacyguard listed with no errors.
2. Type `/hooks`. Look for: SessionStart, UserPromptSubmit, PreToolUse, PostToolUse and Stop with source `[plugin:legacyguard]`.
3. Type `/mcp`. Look for: the guard server connected.

## MC-3 API key warning in a live session (E2E-8)

Verified offline only: the build rules forbid setting `ANTHROPIC_API_KEY` on a Claude session. To see it live, use a fake value so nothing can be billed.

1. `cd demo/billing-api`
2. `ANTHROPIC_API_KEY=not-a-real-key claude --plugin-dir ../../legacyguard`
3. Look for: the `ANTHROPIC_API_KEY is set` notice at the start. Claude may then refuse to answer, because the key is invalid. That is expected.
4. Quit, and confirm the variable isn't set in your shell.

## MC-4 What the developer sees for a wake-up (FR-15)

Async output goes to Claude, not the developer (OQ-B5 evidence). So check how visible a wake-up is.

1. Run the E2E-1 prompt from docs/DEMO_SCRIPT.md in an interactive session.
2. Look for: Claude reacting to the counterexample without you typing anything, then the Stop summary line.
3. Type `/legacyguard:status`. Look for: `turned back` next to `compute_late_fee`.
4. Decide whether this is visible enough for the demo.
5. Open the newest file in `.legacyguard/reports/` and time yourself. Look for: you can tell what was checked and what wasn't in about 10 seconds (TESTING.md §10, item 7).

## MC-5 Waive and pin by hand (FR-24, FR-25)

1. Apply the rounding edit, then type `/legacyguard:waive LG-1 "finance asked for it"`. Look for: `Waived LG-1`, and an entry in `.legacyguard/waivers.json`.
2. Type `/legacyguard:pin LG-1`. Look for: `tests/legacyguard/test_pinned_LG_1.py`.
3. Run `.venv/bin/python -m pytest -q tests/legacyguard`. Look for: it fails while `round()` is in place.

## MC-6 Pitch rehearsal and backup video (M8)

1. Follow docs/DEMO_SCRIPT.md with a timer. Target: 2.5 minutes.
2. Record the screen for a backup video.
3. Run it on the demo machine and network, since the first session start builds the venv.

## MC-7 Team decisions the build could not make

1. OQ-N10: does the pitch lead with everyday agent safety or legacy modernization?
2. OQ-N11: team roles for the Team rubric criterion.
3. OQ-N12: GitHub org and repo for the marketplace. Then replace `<owner>/<repo>` in `legacyguard/README.md`.
