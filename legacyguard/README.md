# legacyguard

A Claude Code plugin that guards one Python backend service. See the project's `docs/` for the design.

```bash
claude plugin validate ./legacyguard
claude --plugin-dir ./legacyguard
```

In the guarded repo, add `.legacyguard/config.yaml` and run `/legacyguard:index`.
