---
id: T03
parent: S03
milestone: M001
provides:
  - explicit recovery classification for recoverable, terminal, retry, replay, and terminate-after-partial-success sync states
  - replay lineage generations that append durable sync history instead of mutating prior rows
  - terminal workflow snapshots that preserve partial sync success counts and last attempted item references
requires: []
affects: []
key_files: []
key_decisions: []
patterns_established: []
observability_surfaces: []
drill_down_paths: []
duration: 10 min
verification_result: passed
completed_at: 2026-03-12
blocker_discovered: false
---
# T03: 03-adapter-writes-and-recovery-guarantees 03

**# Phase 3 Plan 3: Recovery Lineage Summary**

## What Happened

# Phase 3 Plan 3: Recovery Lineage Summary

**Explicit replay lineage generations, durable recovery classifications, and terminate-after-partial-success snapshots for workflow sync execution**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-12T22:43:00Z
- **Completed:** 2026-03-12T22:53:24Z
- **Tasks:** 3
- **Files modified:** 11

## Accomplishments
- Added durable recovery metadata to sync records so recoverable failures, terminal failures, retry requests, replay requests, and terminate-after-partial-success states are queryable from storage.
- Introduced replay lineage generation and explicit replay-request workflow events so operator-intended re-execution stays distinct from same-run retry.
- Preserved partial-sync success on termination by cancelling remaining work, recording partial counts, and preventing later sync execution from resuming a terminated run.

## Task Commits

Each task was committed atomically:

1. **Task 1: Persist recovery classification and replay lineage separately from retry** - `2f28fae` (feat)
2. **Task 2: Preserve partial-sync lineage when termination halts remaining writes** - `d61ef47` (feat)
3. **Task 3: Keep replay and same-run retry semantics distinct in tests and durable events** - `5fab3d2` (test)

## Files Created/Modified
- `migrations/versions/20260313_0012_workflow_recovery_lineage.py` - Adds recovery metadata columns and lineage generation support to `workflow_sync_records`.
- `packages/storage/src/helm_storage/models.py` - Extends the sync ORM with replay generation, recovery classification, and termination snapshot fields.
- `packages/storage/src/helm_storage/repositories/contracts.py` - Exposes typed recovery classification and sync lineage queries to the storage layer.
- `packages/storage/src/helm_storage/repositories/workflow_sync_records.py` - Persists recovery metadata, lineage generation, and success/failure transitions.
- `packages/storage/src/helm_storage/repositories/replay_queue.py` - Adds workflow sync replay queue entries distinct from generic agent-run replay items.
- `packages/orchestration/src/helm_orchestration/schemas.py` - Adds typed recovery transition and replay request payloads for durable workflow events.
- `packages/orchestration/src/helm_orchestration/workflow_service.py` - Records retry, replay, recoverable, terminal, and terminate-after-partial-success semantics explicitly in storage and events.
- `tests/unit/test_workflow_orchestration_service.py` - Verifies retry vs replay lineage, terminal failure classification, and terminate-after-partial-success behavior.
- `tests/unit/test_workflow_repositories.py` - Verifies sync repository durability for recovery metadata and termination snapshots.

## Decisions Made
- Replay was modeled as a new sync lineage generation because the existing uniqueness constraint on `(proposal, version, target, kind, planned_item_key)` would otherwise force history to be overwritten.
- Recovery state was stored on sync rows and repeated in workflow events so later status projection work can query durable facts directly.
- Termination cancels only non-succeeded sync rows and leaves already-succeeded rows untouched to preserve outbound write lineage.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added a follow-on recovery migration instead of reusing `20260313_0011`**
- **Found during:** Task 1 (Persist recovery classification and replay lineage separately from retry)
- **Issue:** The plan referenced `migrations/versions/20260313_0011_workflow_recovery_lineage.py`, but the repo already had `20260313_0011_workflow_sync_execution.py`.
- **Fix:** Added `20260313_0012_workflow_recovery_lineage.py` as the next Alembic revision and preserved the existing migration chain.
- **Files modified:** `migrations/versions/20260313_0012_workflow_recovery_lineage.py`
- **Verification:** Full unit suite for workflow orchestration and repositories passed.
- **Committed in:** `2f28fae`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** No scope change. The deviation only preserved migration correctness in the existing repository state.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Recovery and replay semantics are now explicit enough for status projection and operator entrypoints to consume durable facts directly in Plans `03-04` and `03-05`.
- API and Telegram surfaces can rely on stored recovery classification, replay lineage generation, and termination snapshots instead of inferring operator-safe actions from error text.

## Self-Check
PASSED
- Found `.planning/phases/03-adapter-writes-and-recovery-guarantees/03-03-SUMMARY.md`
- Verified commits `2f28fae`, `d61ef47`, and `5fab3d2` exist in git history

---
*Phase: 03-adapter-writes-and-recovery-guarantees*
*Completed: 2026-03-12*
