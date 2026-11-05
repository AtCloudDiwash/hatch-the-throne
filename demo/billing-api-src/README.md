# billing-api

Billing service: customers, invoices, payments, credit notes, late fees and month-end close.

```bash
.venv/bin/python -m pytest -q           # run the tests
.venv/bin/uvicorn billing.api.app:app   # run the API, if uvicorn is installed
```

Layout: `billing/` business rules, `billing/api/` HTTP routes, `jobs/` scheduled jobs, `reports/` reporting,
`legacy/` the old general-ledger module, `migrations/` schema history, `db/rates.sql` rate data,
`schemas/events/` event schemas, `openapi.yaml` the published API contract.
