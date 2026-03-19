# S02 Roadmap Assessment

**Verdict: Roadmap is unchanged. Remaining slices S03–S06 are valid as written.**

## S02 Delivery vs. Plan

S02 delivered everything the boundary map promised:
- `CalendarProvider` + `InboxProvider` structural Protocols
- `GoogleCalendarProvider(user_id, db)` + `GmailProvider(user_id, db)` satisfying those protocols
- `ProviderFactory(user_id, db)` with `.calendar()` and `.inbox()` entry points
- `build_google_credentials()` with OAuth refresh + DB write-back
- All four data classes (`NormalizedGmailMessage`, `PullMessagesReport`, `GmailSendResult`, `GmailSendError`) re-exported from `helm_providers.gmail` with identical field signatures to the bespoke connector
- 42 unit tests, 0 ruff errors

The key milestone risk ("per-user credential injection into google_workspace_mcp") is retired via the gauth bypass pattern (D023): `__new__` allocation + `_service` injection bypasses `gauth.get_credentials()` entirely. The proof strategy item for S02 is satisfied at the contract/unit level; real-credential smoke test remains deferred to S04 (calendar) and S05 (Gmail) as planned.

## Risk Retirement

| Risk | Status |
|------|--------|
| Per-user credential injection viability | ✅ Retired — `__new__` + `_service` pattern confirmed clean; D023 locked |
| Authlib dependency for token refresh | ✅ Retired — `google-auth` (already transitive) used instead; D024 locked |
| Circular import from protocols referencing gmail types | ✅ Retired — TYPE_CHECKING guard pattern in place |

## Boundary Contract Verification

All downstream slice contracts are satisfied:

- **S03** needs `CalendarProvider` protocol + `GoogleCalendarProvider` → both present; `from helm_providers import GoogleCalendarProvider, CalendarProvider` works
- **S04** needs `GoogleCalendarProvider` to replace `GoogleCalendarAdapter` in worker + bot → present; constructor `GoogleCalendarProvider(user_id, db)` handles all credential plumbing internally
- **S05** needs `GmailProvider` + data classes with identical field names → present; S05 can do a one-line import path swap with no downstream code changes
- **S06** needs `CalendarProvider` + `InboxProvider` Protocol classes for finalization → present in `packages/providers/src/helm_providers/protocols.py`

## Success Criterion Coverage

All six milestone success criteria remain covered by at least one remaining slice:

- `/task` and `/agenda` via MCP-backed calendar tools → S03, S04
- Email pipeline via MCP Gmail tools → S05
- `packages/connectors/` deleted → S06
- `users`/`user_credentials` tables + bootstrap → S01 ✓ complete
- All tests pass → S04, S05, S06
- `CalendarProvider` + `InboxProvider` protocols exist with satisfying implementations → S02 ✓ complete
- Demo flows from M004 UAT still work → S04, S05, S06

## Requirement Coverage

No active requirements are directly changed by this assessment. S02 establishes the provider layer that S04 and S05 need to validate connector-replacement requirements. All existing validated requirements (R100–R118) remain unaffected. No requirements surfaced, invalidated, or re-scoped.

## One Fragility to Watch (S05)

`GmailProvider.send_reply()` reads `creds.email` for the sender address. S01's `bootstrap_user()` must populate the `email` column on `user_credentials`. If that field is NULL, sends fail with a None From address. S05 should verify `email` is populated before running end-to-end email tests. No slice change needed — already noted in S02's forward intelligence.

## Slice Ordering

S03 → S04 → S05 → S06 dependency chain is intact and unchanged. No reordering, merging, or splitting warranted.
