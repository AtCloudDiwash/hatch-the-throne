# Demo script (2.5 minutes)

Prepare beforehand, in a terminal with a large font:

```bash
python3 demo/build_billing_repo.py
cd demo/billing-api
../../.venv/bin/python ../../legacyguard/scripts/lg.py index
claude --plugin-dir ../../legacyguard
```

| Time | Say | Do |
| --- | --- | --- |
| 0:00 | "An agent says 'Done, all tests pass.' Two days later something breaks in a file it never mentioned. Most agent-changed lines are never executed by tests." | Show `billing/fees.py` |
| 0:20 | "The agent is smart. It lacks evidence. So the old code becomes the oracle." | Type the E2E-1 prompt below |
| 0:35 | "All 45 tests still pass with this edit. But the guard ran old and new code on the same inputs." | Point at the counterexample: 40.20 at 2.5% is 1.01 before, 1.00 after |
| 1:00 | "The counterexample came from a real test's arguments. Claude reverts without me saying anything, and the guard proves the fix by running it again." | Show the turned-back line |
| 1:20 | "A contract break is the one thing that interrupts a person." | Type: `Remove the currency field from InvoiceOut`. Show the `[plugin:legacyguard]` prompt |
| 1:45 | "And it is honest about what it did not check." | `/legacyguard:status`: point at `Untested` |
| 2:00 | Give the measured numbers from docs/FINAL_REPORT.md, including the misses | |
| 2:20 | "Legacy systems have no spec, and the old code is the most trusted oracle. That is where this goes." | |

E2E-1 prompt:

```text
Apply this exact edit to billing/fees.py first, with the Edit tool: replace `fee = fee.quantize(CENT, ROUND_HALF_UP)` with `fee = round(fee, 2)`. Customer-facing fee amounts must stay what they were before this edit, so make sure that still holds before you finish.
```

Do not say "safe". Do not give a dollar figure for regressions, or compare agents to humans: no evidence was found for either (PRODUCT.md §1).

Why the prompt names the edit: in two live runs, Sonnet left the rounding alone when asked to simplify the code, and refused `round()` when asked for it. The guard stayed quiet both times, which is correct. A trap demo needs the edit to happen.
