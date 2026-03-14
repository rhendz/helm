# S04: External-Change Truth, Reconciliation Policy, and Operator-Safe Recovery

**Reconciliation policy is locked in, recovery classifications enable safe operator actions, partial failures are handled transparently, and no silent corruption paths remain. Drift-detected workflows can be safely recovered via retry or replay.**

## Slice Goal

When Helm detects drift (S02), the system must respond in an operator-safe way: drift is visible to the operator, recovery actions are explicit and available, partial failures don't corrupt state silently, and the operator can recover via retry or replay without risk. This slice hardens M003 against edge cases and earning operator trust through transparent recovery.

## Must-Haves

- [ ] Recovery classification assigned to DRIFT_DETECTED sync records (enables safe_next_actions)
- [ ] Drift-detected records map to retriable/terminal/proposal-required actions in workflow status service
- [ ] Reconciliation policy is decided and documented: passive (operator initiates recovery) vs active (Helm proposes)
- [ ] Partial failure handling strategy is documented: "leave dirty" with termination snapshots and partial counts preserved
- [ ] Integration tests prove drift-to-retry and drift-to-replay workflows execute safely without silent corruption
- [ ] Operator sees clear recovery action descriptions in Telegram (not just action names)
- [ ] UAT script enables operator to verify drift detection, recovery actions, and successful reconciliation in their own environment

## Requirements Coverage

- **R011 (External-change detection and recovery)** — T02 locks in reconciliation policy; T01 classifies drift records for recovery; T03 proves workflows work
- **R012 (Real-time Telegram visibility)** — T01 determines safe_next_actions for drift; T03 verifies Telegram UX shows recovery options
- **R013 (Operator trust through verification)** — T03 integration tests prove safe recovery paths; UAT script enables operator verification

## Proof Level

- **Contract verification:** Unit tests for recovery classification logic, safe_next_actions mapping
- **Integration verification:** End-to-end tests for drift detection → recovery classification → safe_next_actions → retry/replay workflows
- **Operational verification:** Full workflow runs with real Calendar adapter; Telegram shows recovery actions; operator initiates retry/replay without incident
- **UAT verification:** Operator-runnable script proving drift detection, recovery options, and state reconciliation in their own environment

## Decomposition Rationale

**T01: Recovery Classification (45m)** — Resolves unknown #2 (recovery classification) and unknown #5 (operator visibility). Assigns recovery_classification enum to drifted records and maps to safe_next_actions. Foundation for T03 integration tests. Uses existing patterns from M001 (mark_failed, _safe_next_actions).

**T02: Reconciliation Policy Decision (40m)** — Resolves unknown #1 (passive vs active policy). Decides which recovery actions are safe; documents decision in DECISIONS.md; implements chosen policy (passive most likely). Guides T03 test design.

**T03: Integration Tests and UAT (60m)** — Proves all recovery paths work safely. Creates end-to-end tests for drift → retry, drift → replay, partial failure → terminate. Writes UAT script operator can follow. Validates no silent corruption, all state transitions correct, Telegram UX accurate.

**Risk order:** T01 (easiest, foundation) → T02 (requires decision, shapes T03) → T03 (validation).

## Observability / Diagnostics

- **Recovery classification assignment:** Structured log "recovery_classification_assigned" with sync_record_id, classification, reason
- **Safe actions mapping:** Logs show which sync records receive which safe_next_actions; drift records should map to [request_replay] (passive) or [request_replay, reshuffle_proposal] (active)
- **Partial failure state:** Log "termination_after_partial_sync" with total_writes, task_writes, calendar_writes counts; verify in workflow_events
- **Telegram UX:** Capture formatted status output in integration tests; verify recovery action descriptions are clear (not just enum names)

## Integration Closure

- **Orchestration ↔ Status Service:** Safe actions from orchestration are consumed by status service for API/Telegram projection. T01 wires DRIFT_DETECTED → safe_next_actions. T03 verifies end-to-end.
- **Status Service ↔ Telegram:** Telegram /workflows command reads safe_next_actions and renders recovery buttons. T03 verifies recovery options appear in Telegram output.
- **Orchestration ↔ Recovery:** Operator initiates retry/replay via Telegram; orchestration enqueues new sync lineage. T03 tests full cycle.

## Tasks

### T01: Recovery Classification and Safe Actions Mapping
**Why:** Drift-detected records need recovery classifications so status service can expose safe recovery actions. Currently no classification assigned in _handle_drift_detected().

**Files:**
- `packages/orchestration/src/helm_orchestration/workflow_service.py` (modify: assign recovery_classification in _handle_drift_detected)
- `packages/storage/src/helm_storage/repositories/workflow_sync_records.py` (read: mark_drift_detected method)
- `apps/api/src/helm_api/services/workflow_status_service.py` (modify: add DRIFT_DETECTED → safe_next_actions mapping in _safe_next_actions)
- `packages/storage/src/helm_storage/repositories/contracts.py` (read: recovery_classification enum)
- `tests/unit/test_recovery_classification_for_drift.py` (new: unit tests for classification assignment and action mapping)
- `tests/integration/test_drift_recovery_actions_in_workflow_status.py` (new: integration tests for status service mapping)

**Do:**
1. Read recovery_classification enum in contracts.py; understand existing RECOVERABLE_FAILURE, TERMINAL_FAILURE patterns
2. Read _safe_next_actions() in workflow_status_service.py; understand how classification maps to action names
3. In workflow_service.py _handle_drift_detected(), call mark_drift_detected() then assign recovery_classification
   - Decision: TERMINAL_FAILURE (requires replay) or RECOVERABLE_FAILURE (auto-retry eligible) or new enum?
   - Plan: assume TERMINAL_FAILURE (drift requires human decision, replay respects intent)
   - Call: mark_drift_detected() returns sync_record; then call sync_record.recovery_classification = ... and save
4. In workflow_status_service.py _safe_next_actions(), add case for DRIFT_DETECTED or TERMINAL_FAILURE from drifted records
   - Map to [request_replay] (passive policy — operator initiates recovery)
   - Verify existing [retry, terminate] actions don't leak into drift recovery
5. Write unit tests: classification assignment, mapping consistency, action array correctness
6. Write integration tests: full workflow status projection with drifted records shows correct recovery actions
7. Verify: ruff, mypy, black all pass; tests pass; no regressions

**Verify:**
- [ ] Drifted sync records have recovery_classification set (not null)
- [ ] recovery_classification = TERMINAL_FAILURE (if passive policy chosen)
- [ ] _safe_next_actions() returns [request_replay] for TERMINAL_FAILURE records from drift
- [ ] Existing retry/terminate actions don't appear for drifted records
- [ ] All 5 unit tests pass (classification assignment, action mapping, edge cases)
- [ ] All 2 integration tests pass (status projection with drifted records)
- [ ] Zero regressions (full suite green)

**Done when:** Drifted sync records properly classified; recovery actions visible in API/Telegram; no regressions.

---

### T02: Reconciliation Policy Decision and Documentation
**Why:** S02 detected drift; S04 must decide *how Helm responds*: wait for operator (passive) or auto-propose reshuffle (active). This shapes recovery action names, Telegram messages, and operator experience.

**Files:**
- `.gsd/DECISIONS.md` (append: reconciliation policy decision with rationale, examples, alternatives considered)
- `packages/orchestration/src/helm_orchestration/workflow_service.py` (read/verify: _handle_drift_detected implementation matches policy)
- `docs/internal/helm-v1.md` (read: confirm V1 scope, no requirement for active proposals)

**Do:**
1. Review S04 research section "1. Reconciliation Policy: Passive vs. Active" for unknowns and constraints
2. Review existing patterns: M001 established safe_next_actions for operator-initiated recovery (retry, replay, etc.)
3. Analyze constraints:
   - "Operator-safe recovery means no silent rewrites; explicit proposal is required" (M003 context) → favors passive
   - R011: "Helm is an assistant, not an enforcer. Without this, Helm becomes adversarial." → favors passive
   - Current recovery system allows passive retry/replay; active proposal generation not yet implemented → passive is lower-effort
4. Decision: **Passive reconciliation policy** — Helm detects drift, marks it, exposes recovery actions (request_replay, request_reshuffle if needed), operator chooses
   - Alternative considered (active): auto-generate proposal, pause workflow, wait for approval — higher implementation cost, defers to future phases
5. Document decision in DECISIONS.md with:
   - Policy statement: "When drift is detected, Helm exposes operator-initiated recovery actions (request_replay) rather than auto-proposing rewrites. This respects operator intent and prevents adversarial behavior."
   - Rationale: simpler, aligns with M001 philosophy, matches existing safe_next_actions pattern
   - Examples: operator reschedules event → Helm detects drift → marks sync record → exposes [request_replay] action → operator clicks to initiate recovery
   - Alternatives: active proposal (deferred to future phases due to implementation complexity and UI design work)
6. Verify orchestration already implements passive handling: _handle_drift_detected() continues workflow without blocking, drift event created, record marked — this matches passive pattern
7. No code changes needed if passive policy is already implemented; decision documents what's already built

**Verify:**
- [ ] Decision entry appended to DECISIONS.md (policy, rationale, examples, alternatives)
- [ ] Decision statement is clear and unambiguous (no "maybe" or "might")
- [ ] Examples in decision show concrete operator interaction (drift detection → operator sees action → recovery choice)
- [ ] Orchestration implementation already matches passive pattern (no code changes needed)
- [ ] No requirements violated by passive choice (R011 actually requires passive, not active)

**Done when:** Reconciliation policy locked in; decision recorded; no ambiguity for S05.

---

### T03: Integration Tests and Operator-Safe Recovery Proof
**Why:** S04 must prove drift-to-recovery workflows execute safely without silent corruption. Integration tests validate all recovery paths; UAT script enables operator verification in their own environment.

**Files:**
- `tests/integration/test_drift_recovery_workflows.py` (new: comprehensive drift → retry/replay integration tests)
- `.gsd/milestones/M003/slices/S04/S04-UAT.md` (new: UAT script operator follows to verify drift detection and recovery)
- `packages/storage/src/helm_storage/repositories/workflow_sync_records.py` (read: query methods for drift records)
- `packages/orchestration/src/helm_orchestration/workflow_service.py` (read: full reconciliation and recovery flow)
- `apps/api/src/helm_api/services/workflow_status_service.py` (read: recovery action projection)

**Do:**
1. Plan integration test scenarios:
   - **Scenario A: Drift → Request Replay** — Sync record in UNCERTAIN_NEEDS_RECONCILIATION → reconciliation detects drift → record marked DRIFT_DETECTED → safe_next_actions includes request_replay → operator requests replay → new sync lineage created → retry succeeds (mocked Calendar returns updated event matching new intent)
   - **Scenario B: Partial Failure → Terminate** — Sync A succeeds, Sync B fails (calendar down), Sync C not attempted → workflow terminated → TERMINATED_AFTER_PARTIAL_SUCCESS recorded with counts → operator sees partial counts in status → can request replay
   - **Scenario C: Drift + Manual Edit Recovery** — Drift detected → operator doesn't initiate replay immediately → operator manually edits Calendar event back to Helm's intent → Helm detects new drift (event now matches stored payload) → reconciliation marks SUCCEEDED (or DRIFT_RESOLVED if new status added)
   - **Scenario D: Multiple Syncs, Some Drift** — 3 syncs in same lineage: A succeeds, B drifts, C succeeds → workflow completes with mixed outcomes → status projection shows 2 succeeded, 1 drifted, recovery actions appropriate per record type
   - **Scenario E: Replay After Drift** — Drift detected → request_replay issued → new sync lineage scoped to drifted records → reconciliation now matches (mocked Calendar unchanged) → new lineage syncs succeed → old lineage shows drift history, new lineage shows success
2. Write test_drift_request_replay() for Scenario A:
   - Setup: sync record ready for reconciliation, mock adapter returns drift
   - Execute: call orchestration step, trigger reconciliation
   - Assert: record status=DRIFT_DETECTED, recovery_classification=TERMINAL_FAILURE, safe_next_actions=[request_replay], drift_event created
3. Write test_partial_failure_termination() for Scenario B:
   - Setup: 3 sync records, mock adapters: A succeeds, B fails, C pending
   - Execute: fail B, trigger termination
   - Assert: A=SUCCEEDED, B=FAILED_TERMINAL, C=CANCELLED, termination_summary has counts, safe_next_actions=[request_replay]
4. Write test_drift_then_operator_fixes() for Scenario C (if time; stretch goal):
   - Setup: drift detected, operator manually edits Calendar
   - Execute: reconcile again after operator edit
   - Assert: detect that edit matches stored payload (no longer drift); mark SUCCEEDED or DRIFT_RESOLVED
5. Write test_mixed_outcomes_in_workflow() for Scenario D:
   - Setup: 3 syncs, mock outcomes: success, drift, success
   - Execute: full sync lineage
   - Assert: status projection shows 2 succeeded + 1 drifted; recovery actions appropriate per record; total counts correct
6. Write test_replay_after_drift() for Scenario E:
   - Setup: initial sync drifts; request replay issued
   - Execute: new sync lineage created from approved proposal; reconciliation runs
   - Assert: new lineage syncs succeed; drift history preserved in old lineage; no silent data loss
7. Write UAT script `.gsd/milestones/M003/slices/S04/S04-UAT.md`:
   - Prerequisites: operator's own Google Calendar access, credentials configured, Helm running locally or deployed
   - Steps:
     1. Create test event in Helm (propose + approve via API/Telegram)
     2. Verify event appears on operator's Google Calendar
     3. Operator manually reschedules event in Calendar app (change start time)
     4. Trigger sync reconciliation (run sync step or wait for polling)
     5. Verify Helm detects drift: drift event created, sync record marked DRIFT_DETECTED
     6. Verify Telegram shows recovery action (request_replay button or command)
     7. Operator initiates recovery (click button or run command)
     8. Verify new sync lineage created and reconciliation proceeds
     9. Verify Calendar event is now in sync with Helm's intent (or operator's edit is preserved if replay respects manual change)
   - Expected outcome: drift detected, recovery initiated, state reconciled, operator sees durable event history
   - Verification: query database for drift_detected_external_change event, check sync record status transitions, confirm Telegram message sent
8. Run all new tests; verify zero regressions; verify ruff, mypy, black pass

**Verify:**
- [ ] test_drift_request_replay passes: drift detected, recovery_classification set, request_replay available
- [ ] test_partial_failure_termination passes: termination snapshot captures correct counts, recovery actions available
- [ ] test_mixed_outcomes_in_workflow passes: status projection handles mixed success/drift correctly
- [ ] test_replay_after_drift passes: new lineage created, drift history preserved, no data loss
- [ ] All integration tests pass (5 scenarios, all green)
- [ ] UAT script is operator-readable and follows logical steps (prerequisite → action → verification)
- [ ] UAT script includes explicit queries/commands to verify state (not just "you should see X")
- [ ] Zero regressions (full suite passes)
- [ ] Structured logs verify all state transitions (UNCERTAIN → DRIFT_DETECTED → replay triggered, etc.)

**Done when:** All 5 integration test scenarios pass; UAT script proven readable and actionable; no silent corruption paths remain; operator can follow UAT script to verify behavior in their own environment.

---

## Verification

**Test files:**
- `tests/unit/test_recovery_classification_for_drift.py` — 5 unit tests for classification logic
- `tests/integration/test_drift_recovery_actions_in_workflow_status.py` — 2 integration tests for status service mapping
- `tests/integration/test_drift_recovery_workflows.py` — 5 comprehensive integration tests (Scenario A–E)

**Test command:**
```bash
scripts/test.sh
```

**Success criteria:**
- All 12 new tests pass
- Zero regressions (full suite green)
- UAT script is present and readable
- All structured logs are produced (recovery_classification_assigned, termination_after_partial_sync, etc.)
- Decisions appended to DECISIONS.md

## Definition of Done

- [ ] T01 complete: recovery classification assigned, safe_next_actions mapped, tests pass, no regressions
- [ ] T02 complete: reconciliation policy decided, decision documented in DECISIONS.md
- [ ] T03 complete: 5 integration test scenarios pass, UAT script written and verified readable, structured logs captured
- [ ] All requirements advanced: R011/R012/R013 supported by T01/T02/T03
- [ ] Slice verification passed: `scripts/test.sh` all green, ruff/mypy/black pass
- [ ] Commit: `docs(S04): plan complete, all must-haves met, ready for execution`
- [ ] Update `.gsd/STATE.md` to mark S04 planned

---

## Slice Boundary

**Consumes (from S01, S02, M001):**
- GoogleCalendarAdapter with reconcile_calendar_block() (S01)
- Drift detection and DRIFT_DETECTED status (S02)
- Existing recovery_classification enum and safe_next_actions pattern (M001)
- Workflow orchestration and sync record persistence (M001)

**Produces (for S03, S05):**
- Recovery classification assigned to all sync record types (drift, failure, success)
- Safe_next_actions mapping for all recovery classifications (drift → request_replay)
- Reconciliation policy documented (passive)
- Integration tests proving drift → recovery → retry/replay workflows execute safely
- UAT script enabling operator verification of drift detection and recovery

**No new contracts introduced.** S04 uses existing RecoveryClassification enum, CalendarSystemAdapter protocol, and WorkflowSyncStatus — all from M001/S01/S02.

