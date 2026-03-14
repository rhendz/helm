# M003: Task/Calendar Productionization

**Vision:** Real Google Calendar integration, external-change detection and recovery, real-time operator visibility, and explicit operator trust through verification. Move the task/calendar workflow from demo to production-ready usefulness.

## Success Criteria

- Operator can authenticate to their Google Calendar and run the weekly scheduling workflow end-to-end with real Calendar events appearing
- Operator can manually reschedule a Calendar event; Helm detects the change and reconciles internal state without fighting the operator
- Telegram shows real-time sync progress, failures, and recovery options as tasks and events flow to external systems
- Comprehensive automated tests and UAT scripts prove drift detection, reconciliation, and recovery all work correctly
- Operator can read UAT script and verify these outcomes in their own environment

## Key Risks / Unknowns

- **Google Calendar API auth:** Service account vs user OAuth shapes integration architecture. Decision in S01.
- **Drift detection efficiency:** Polling vs webhooks affects API load and latency. Decision in S02.
- **Reconciliation policy:** Context-dependent active vs passive logic requires careful design. Decision in S04.
- **Partial failure semantics:** Roll back or leave dirty? Affects operator trust and recovery complexity. Decision in S04.

## Proof Strategy

- **Google Calendar auth architecture** → retire in S01 by implementing both read and write to real Calendar with chosen auth method
- **Drift detection reliability** → retire in S02 by detecting manual calendar edits and proving internal reconciliation
- **Operator trust under failure** → retire in S04 by handling partial failures safely without silent corruption
- **Real end-to-end usability** → retire in S05 by running full weekly scheduling workflow with real Calendar access and Telegram visibility

## Verification Classes

- **Contract verification:** Unit tests for Calendar adapter methods, reconciliation logic, auth credential handling
- **Integration verification:** Real Calendar API calls (or fixtures) in integration tests; sync records reflect actual external outcomes
- **Operational verification:** Full workflow runs with real Calendar access; Telegram receives and displays status updates; drift detection works on live Calendar state
- **UAT / human verification:** Operator follows UAT script to verify their own environment: auth works, workflow runs, drift is detected and reconciled

## Milestone Definition of Done

This milestone is complete only when all are true:

- Google Calendar adapter is real (not stub); reads and writes work with chosen auth method
- External-change detection works end-to-end: operator edits Calendar, Helm detects it, internal state is reconciled
- Telegram displays real-time sync status, failures, and recovery options
- Automated tests cover Calendar operations, reconciliation, partial failures, and recovery paths
- End-to-end weekly scheduling workflow with real Calendar writes passes integration tests
- UAT script exists and is verified by operator in their own environment
- All changes are merged to main with passing CI

## Requirement Coverage

- Covers: R006 (auth decision), R010 (real Calendar sync), R011 (drift detection), R012 (Telegram visibility), R013 (verification)
- Partially covers: none
- Leaves for later: R020 (additional workflows), R030 (web UI)
- Orphan risks: none

## Slices

- [x] **S01: Google Calendar Auth and Real Read/Write Adapter** `risk:high` `depends:[]`
  > After this: Helm can authenticate to Google Calendar (service account or OAuth) and write test events; operator can see them in their real calendar.

- [x] **S02: External-Change Detection and Sync State Reconciliation** `risk:medium` `depends:[S01]`
  > After this: Operator manually reschedules a Calendar event; Helm detects the change and updates internal model without fighting the edit.

- [x] **S03: Telegram Real-Time Execution UX** `risk:medium` `depends:[S01,S02]`
  > After this: Running a workflow shows real-time sync progress in Telegram: tasks/events flowing, failures visible, recovery actions clear.

- [x] **S04: External-Change Truth, Reconciliation Policy, and Operator-Safe Recovery** `risk:medium` `depends:[S01,S02]`
  > After this: Helm handles partial failures safely, reconciliation policy is explicit, operator-safe recovery is proven (no silent corruption).

- [x] **S05: End-to-End Integration Verification and UAT** `risk:low` `depends:[S01,S02,S03,S04]`
  > After this: Full weekly scheduling workflow runs end-to-end with real Calendar writes, drift handling, Telegram visibility; operator can verify outcomes in their own environment.

<!--
  Format rules (parsers depend on this exact structure):
  - Checkbox line: - [ ] **S01: Title** `risk:high|medium|low` `depends:[S01,S02]`
  - Demo line:     >  After this: one sentence showing what's demoable
  - Mark done:     change [ ] to [x]
  - Order slices by risk (highest first)
  - Each slice must be a vertical, demoable increment — not a layer
  - If all slices are completed exactly as written, the milestone's promised outcome should actually work at the stated proof level
  - depends:[X,Y] means X and Y must be done before this slice starts
  
  Planning quality rules:
  - Every slice must ship real, working, demoable code — no research-only or foundation-only slices
  - Early slices should prove the hardest thing works by building through the uncertain path
  - Each slice should establish a stable surface that downstream slices can depend on
  - Demo lines should describe concrete, verifiable evidence — not vague claims
  - In brownfield projects, ground slices in existing modules and patterns
  - If a slice doesn't produce something testable end-to-end, it's probably a layer — restructure it
  - If the milestone crosses multiple runtime boundaries (for example daemon + API + UI, bot + subprocess + service manager, or extension + RPC + filesystem), include an explicit final integration slice that proves the assembled system works end-to-end in a real environment
  - Contract or fixture proof does not replace final assembly proof when the user-visible outcome depends on live wiring
  - Each "After this" line must be truthful about proof level: if only fixtures or tests prove it, say so; do not imply the user can already perform the live end-to-end behavior unless that has actually been exercised
-->

## Boundary Map

### S01 → S02

Produces:
- `GoogleCalendarAdapter` class with `upsert_calendar_block(CalendarSyncRequest) -> CalendarSyncResult` and `reconcile_calendar_block(SyncLookupRequest) -> SyncLookupResult` (replaces StubCalendarSystemAdapter)
- Auth credential handling (service account or OAuth) with refresh/expiry logic
- Google Calendar API client initialization and error handling
- Integration point: accepts `CalendarSyncRequest` with event details (title, start, end, etc.)
- Returns: `CalendarSyncResult` with external_object_id (Google Calendar event ID), status, retry disposition
- Test fixtures: mock Calendar API responses for contract verification

Consumes:
- nothing (first slice)

### S01 → S03

Produces:
- Real Calendar adapter working correctly (from S01)
- Sync contracts and schemas already defined (from M001)

Consumes:
- nothing new (uses existing sync contracts)

### S02 → S03, S04

Produces:
- Drift detection logic: compare stored payload fingerprint with live Calendar event state
- Reconciliation model: when drift is detected, update internal `workflow_sync_records` to reflect new truth
- Policy decision logged in `.gsd/DECISIONS.md`: polling vs webhook, detection latency
- Integration point: `reconcile_calendar_block()` returns updated `SyncLookupResult` with `payload_fingerprint_matches=false` when drift detected

Consumes:
- GoogleCalendarAdapter from S01
- Existing sync record schema from M001

### S03 → S05

Produces:
- Telegram status formatter extensions: sync event streaming (upsert success/failure, drift detection, reconciliation)
- Workflow status projection enriched with real-time sync facts (instead of just completion summary)
- Integration point: Telegram commands receive sync events and render them as chat messages
- Message contract: "Event X scheduled on calendar at time Y", "Event X detected drift (manual reschedule)", "Reconciling internal state...", "Recovery action: propose reshuffle"

Consumes:
- Existing workflow status service from M001
- Existing Telegram command handlers from M001

### S04 → S05

Produces:
- Partial failure handling logic: what happens when task sync succeeds but calendar fails (or vice versa)
- Recovery classification: retriable, terminal, safe-to-ignore, requires-operator-action
- Explicit reconciliation policy: passive observation vs active proposal triggers
- Test fixtures: scenarios for conflict resolution, partial failures, retry behavior
- Updated sync record schema interpretation (if needed)

Consumes:
- Drift detection and reconciliation from S02
- Calendar adapter from S01
- Existing sync record schema from M001

### S05 (Integration)

Produces:
- End-to-end integration test: full weekly scheduling workflow with real Calendar adapter and Telegram mocking
- UAT script: operator-runnable verification of auth, drift detection, sync visibility, recovery
- Completion summary: what was proven, what remains uncertain, what's safe for operator use
- No new contracts; proves all prior slices work together

Consumes:
- All prior slices: Calendar adapter (S01), drift detection (S02), Telegram UX (S03), recovery policy (S04)
