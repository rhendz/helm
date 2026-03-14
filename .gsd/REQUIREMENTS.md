# Requirements

## Validated

- **REQ-DURABLE-PERSISTENCE**: Durable workflow runs, steps, artifacts, and lineage are persisted and inspectable — validated in M001 (S01 established core tables with typed repositories and hermetic test coverage).
- **REQ-SPECIALIST-DISPATCH**: Typed TaskAgent and CalendarAgent dispatch with durable invocation records — validated in M001 (specialist invocation table with input/output artifact linkage).
- **REQ-APPROVAL-CHECKPOINTS**: Approval checkpoints, revision-driven proposal versioning, and kernel-owned resume semantics — validated in M001.
- **REQ-ADAPTER-SYNC**: Adapter-gated sync execution with idempotency, retry, replay, and recovery classification — validated in M001.
- **REQ-REPRESENTATIVE-WORKFLOW**: Representative weekly scheduling workflow from request through approved writes and replay-aware final lineage — validated in M001.
- **REQ-OPERATOR-SURFACES**: Telegram and API operator tooling for workflow status, approval, replay, and lineage inspection — validated in M001.
- **R002** — Repo working set is reduced to active and frozen truth
  - Class: continuity
  - Status: validated
  - Description: S02 physically quarantined aspirational domain code, constrained Night Runner to deprecated scripts plus archived docs, confirmed LinkedIn has no live implementation, and kept tests/CI green without relying on these paths.
  - Why it matters: Reduces cognitive load and prevents future work from building on dead paths just because files remain in the tree.
  - Source: user
  - Primary owning slice: M002/S02
  - Supporting slices: M002/S01, M002/S03
  - Validation: validated
  - Notes: Classification inventory and rg-based diagnostics provide the ongoing guardrail.
- **R005** — Deprecated paths are clearly marked and removed where safe
  - Class: failure-visibility
  - Status: validated
  - Description: LinkedIn, Night Runner, and packages/domain are explicitly classified as deprecated/quarantined, removed from live import paths, and discoverable via diagnostics.
  - Why it matters: Prevents future milestones from seeing these paths as live options and reduces risk of accidentally reviving deprecated architecture.
  - Source: user
  - Primary owning slice: M002/S02
  - Supporting slices: M002/S01
  - Validation: validated
  - Notes: docs/archive/, the classification inventory, and rg sweeps are the authoritative signals for deprecated surfaces.

## Active

### R006 — Google Calendar auth model is selected and implemented
- Class: core-capability
- Status: validated
- Description: User OAuth 2.0 model chosen and fully implemented. GoogleCalendarAuth handles credential lifecycle (init, token refresh, error classification). Operator self-configures credentials (client_id, client_secret, refresh_token) from Google Cloud Console.
- Why it matters: Auth model determines how Helm accesses the operator's calendar, what permissions are needed, token refresh strategy, and what external system state Helm can read/write.
- Source: user
- Primary owning slice: M003/S01
- Supporting slices: none
- Validation: validated
- Notes: S01 implements GoogleCalendarAuth with 17 unit tests covering credential lifecycle. S05 UAT proves operator can configure and verify credentials. Decision: "Google Calendar auth model: use user OAuth (not service account)..." recorded in .gsd/DECISIONS.md.

### R010 — Real bidirectional Google Calendar sync with conflict detection
- Class: integration
- Status: validated
- Description: GoogleCalendarAdapter upsert_calendar_block creates/updates real Calendar events. reconcile_calendar_block reads live state for drift detection. RFC3339 datetime formatting ensures Calendar API compatibility.
- Why it matters: The weekly scheduling workflow is useless if it writes events to a stub system. Real Calendar integration makes the workflow actually runnable and useful.
- Source: user
- Primary owning slice: M003/S01
- Supporting slices: M003/S02, M003/S04
- Validation: validated
- Notes: S01 delivers 10 integration tests for upsert (create/update) and 6 for reconcile (read). S05 happy path test proves weekly scheduling workflow intact. S05 UAT Test Case 1 demonstrates real Calendar write with operator's credentials. Decision: "Calendar adapter protocol: reuse existing CalendarSystemAdapter interface..." recorded in .gsd/DECISIONS.md.

### R011 — External-change detection and recovery
- Class: continuity
- Status: validated
- Description: When the operator manually reschedules or edits a Calendar event that Helm previously wrote, Helm detects the change, reconciles its internal model, and proposes reshuffle actions rather than fighting the operator by rewriting the old plan.
- Why it matters: Operator intent (manual edits) takes precedence. Helm is an assistant, not an enforcer. Without this, Helm becomes adversarial and untrustworthy.
- Source: user
- Primary owning slice: M003/S02
- Supporting slices: M003/S04
- Validation: validated
- Notes: S02 proves drift detection via fingerprint comparison (payload_fingerprint_matches field from adapter reconciliation). Operator edits are detected, field diffs extracted, internal workflow_sync_records marked DRIFT_DETECTED, durable drift events created. Integration tests validate full flow. Reconciliation policy (what Helm does after detecting drift) deferred to S04.

### R012 — Real-time execution visibility in Telegram
- Class: operability
- Status: validated
- Description: TelegramWorkflowStatusService queries sync records and formats timeline with status symbols (✓⚠✗⏳). `/workflows` command shows 8 recent events inline. `/workflow_sync_detail` shows unlimited timeline. Recovery actions (request_replay) visible in status.
- Why it matters: Operator trust depends on visibility. Silent success or hidden failures are equally bad. Real-time Telegram updates make the workflow transparent and actionable.
- Source: user
- Primary owning slice: M003/S03
- Supporting slices: M003/S04, M003/S05
- Validation: validated
- Notes: S03 delivers 31 tests (23 unit + 8 integration). S05 integration test scenario 4 proves sync events queryable and formatted correctly. S05 UAT Test Cases 1-3 demonstrate operator sees sync progress and recovery actions in Telegram. Decision: "Telegram sync timeline limited to 8 events inline..." recorded in .gsd/DECISIONS.md.

### R013 — Operator trust through explicit verification
- Class: quality-attribute
- Status: validated
- Description: S05 delivers 5 integration test scenarios (all pass) proving data correctness and state transitions without silent failures. Operator-runnable UAT script (4 test cases) enables verification in live environment with real Calendar credentials. All state durable and queryable via SQL.
- Why it matters: Since M003 introduces real external state and manual operator edits, trust is earned through transparent, repeatable verification that can be re-checked later.
- Source: user
- Primary owning slice: M003/S05
- Supporting slices: none
- Validation: validated
- Notes: 363 total tests passing (5 new + 358 existing) with zero regressions. S05-UAT.md provides comprehensive operator guidance with prerequisites, step-by-step instructions, SQL verification queries, and troubleshooting. Decision: "Treat weekly scheduling end-to-end behavior as a protected core with dedicated integration tests and a reusable UAT script..." recorded in .gsd/DECISIONS.md.

### R001 — Helm workflow-engine truth set is sharply defined
- Class: core-capability
- Status: active
- Description: The current-version Helm truth set is explicitly defined around the workflow engine, replay/recovery/approvals, task/calendar sync protection, and the Telegram/API/worker surfaces that support those flows.
- Why it matters: Future milestones must not rely on stale, implicit, or aspirational artifacts to infer what Helm is; planning should start from a small, explicit truth set.
- Source: user
- Primary owning slice: M002/S01
- Supporting slices: none yet
- Validation: proofed
- Notes: Truth set is defined in `.gsd/milestones/M002/M002-TRUTH-NOTE.md` (M002/S01) and used as the anchor for classification rules and inventory.

### R003 — Task/calendar workflows remain intact and verified after cleanup
- Class: continuity
- Status: validated
- Description: After truth-set cleanup and artifact removal, the representative weekly scheduling / task+calendar workflows continue to operate correctly through API/worker/Telegram, with explicit verification/UAT demonstrating no regressions.
- Why it matters: Task/calendar sync protection is core truth; cleanup must not break existing behavior.
- Source: user
- Primary owning slice: M002/S03
- Supporting slices: M002/S01, M002/S02
- Validation: validated
- Notes: S03 proves via 14 automated tests (3 integration + 11 unit) and manual UAT that weekly scheduling workflows operate end-to-end through API, worker, and Telegram surfaces after M002 cleanup. Approval checkpoints, sync execution, and completion summaries all verified. UAT script in `.gsd/milestones/M002/slices/S03/S03-UAT.md` enables future verification.

### R004 — Non-core agents do not define current truth
- Class: constraint
- Status: active
- Description: EmailAgent and StudyAgent remain present, but their planning/spec/program artifacts do not define the current-version truth set; StudyAgent is frozen for this version, and Helm-level email planning artifacts are de-scoped as canonical truth.
- Why it matters: Keeps the milestone focused on the workflow-engine truth set and prevents agent-specific plans from quietly steering architecture.
- Source: user
- Primary owning slice: M002/S01
- Supporting slices: M002/S02
- Validation: proofed
- Notes: `.gsd/milestones/M002/M002-TRUTH-NOTE.md` (M002/S01) explicitly treats TaskAgent/CalendarAgent as core truth and EmailAgent/StudyAgent as non-core/frozen; classification rules and inventory in M002 reference this constraint.

## Deferred

### R020 — Additional workflows beyond scheduling
- Class: primary-user-loop
- Status: deferred
- Description: Running additional domain workflows (for example email flows, study flows, or other templates) on the same kernel contract.
- Why it matters: Expands Helm’s capabilities once the truth set is clean, but should not start until M002 has reduced the working set.
- Source: execution
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Seeded from prior M001/M002 vision; will be mapped in a later milestone.

## Out of Scope

### R030 — New primary dashboards or web UIs
- Class: anti-feature
- Status: out-of-scope
- Description: Building a new primary dashboard or web UI that replaces Telegram as the main operator surface.
- Why it matters: Prevents scope creep away from the kernel and task/calendar flows during cleanup.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Telegram remains the primary operator surface for this version.

## Traceability

| ID   | Class              | Status    | Primary owner | Supporting         | Proof      |
|------|--------------------|-----------|---------------|--------------------|------------|
| R001 | core-capability    | active    | M002/S01      | none               | proofed    |
| R002 | continuity         | validated | M002/S02      | M002/S01, M002/S03 | validated  |
| R003 | continuity         | validated | M002/S03      | M002/S01, M002/S02 | validated  |
| R004 | constraint         | active    | M002/S01      | M002/S02           | proofed    |
| R005 | failure-visibility | validated | M002/S02      | M002/S01           | validated  |
| R006 | core-capability    | validated | M003/S01      | none               | validated  |
| R010 | integration        | validated | M003/S01      | M003/S02, M003/S04 | validated  |
| R011 | continuity         | validated | M003/S02      | M003/S04           | validated  |
| R012 | operability        | validated | M003/S03      | M003/S04, M003/S05 | validated  |
| R013 | quality-attribute  | validated | M003/S05      | none               | validated  |
| REQ-DURABLE-PERSISTENCE | core-capability | validated | M001/S01 | none | validated |
| REQ-SPECIALIST-DISPATCH | integration     | validated | M001/S02 | none | validated |
| REQ-APPROVAL-CHECKPOINTS | core-capability | validated | M001/S02 | none | validated |
| REQ-ADAPTER-SYNC        | continuity      | validated | M001/S03 | none | validated |
| REQ-REPRESENTATIVE-WORKFLOW | primary-user-loop | validated | M001/S04 | none | validated |
| REQ-OPERATOR-SURFACES   | operability     | validated | M001/S04 | none | validated |
| R020 | primary-user-loop | deferred  | none          | none               | unmapped   |
| R030 | anti-feature      | out-of-scope | none        | none               | n/a        |

## Coverage Summary

- Active requirements: 2 (R001, R004)
- Validated: 16 (kernel requirements from M001 plus M002/S02 coverage for R002 and R005, plus M002/S03 coverage for R003, plus M003/S01-S05 coverage for R006, R010, R012, R013; plus M003/S02 and M003/S04 coverage for R011)
- Deferred: 1 (R020)
- Out of scope: 1 (R030)
