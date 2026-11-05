# MANUAL_CHECKS.md: steps that need a person at an interactive terminal

These could not be verified with `claude -p`. Each lists what to type and what to look for.

## MC-1 The `ask` prompt label (FR-12, E2E-2)

1. `python3 demo/build_billing_repo.py`
2. `cd demo/billing-api && claude --plugin-dir ../../legacyguard`
3. Type: `Remove the "currency" field from the invoice response in billing/api/invoices.py and from openapi.yaml.`
4. Look for: a permission prompt whose text includes `[plugin:legacyguard]` and names the dropped field.
5. Choose **No**. Look for: Claude explains the contract break, because it also received `additionalContext`.
