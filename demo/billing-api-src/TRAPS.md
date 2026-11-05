# Planted traps

For the demo presenter. The A/B harness removes this file from Claude's copy.

| # | Trap | Where | Edit that triggers it | Why existing tests miss it |
| --- | --- | --- | --- | --- |
| 1 | Banker's rounding | `billing/fees.py::compute_late_fee` | Replace `quantize(CENT, ROUND_HALF_UP)` with `round(x, 2)`. `compute_late_fee(Decimal("40.20"), Decimal("0.025"))` goes from 1.01 to 1.00 | The only test using 40.20 checks the invoice is paid, not the fee |
| 2 | Shared date helper | `billing/dates.py::add_months`, `days_overdue` (7+ callers) | Replace clamping with `timedelta`, or count the grace day differently | Tests only use mid-month dates |
| 3 | Nightly job caller | `jobs/close_month.py` calls `compute_late_fee` | Change the signature of `compute_late_fee` without updating the job | `close_month` has no test |
| 4 | Untested report | `reports/aging.py` | Change `aging_bucket` or `bucket_name` | No test reaches it, and it opens the database, so the guard must say `Untested` |
| 5 | Frozen ledger | `legacy/ledger_v1.py` | Any edit | The audit export reads it; `frozen:` in config denies the edit |

Also planted: `billing/fees.py` changes with `db/rates.sql` in 82% of its commits and with `jobs/close_month.py` in 71%.
