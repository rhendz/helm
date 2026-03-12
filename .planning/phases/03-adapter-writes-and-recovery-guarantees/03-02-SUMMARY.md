---
phase: 03-adapter-writes-and-recovery-guarantees
plan: 02
subsystem: orchestration
tags: [workflow, sync, adapters, retry, recovery, postgres]
requires:
  - phase: 03-01
    provides: Durable approved sync manifest records keyed by proposal version and target system identity
provides:
  - Durable sync attempt metadata and step-attempt scoped repository queries
  - Package-layer task and calendar adapter stubs for deterministic sync dispatch
  - Restart-safe sync resume and retry semantics driven from persisted sync records
affects: [worker, storage, connectors, orchestration, recovery]
tech-stack:
  added: []
  patterns: [reconciliation-first retry, orchestration-owned sync policy, connector boundary stubs]
key-files:
  created:
    - migrations/versions/20260313_0011_workflow_sync_execution.py
    - packages/connectors/src/helm_connectors/task_system.py
    - packages/connectors/src/helm_connectors/calendar_system.py
  modified:
    - packages/storage/src/helm_storage/models.py
    - packages/storage/src/helm_storage/repositories/contracts.py
    - packages/storage/src/helm_storage/repositories/workflow_sync_records.py
    - packages/orchestration/src/helm_orchestration/workflow_service.py
    - packages/orchestration/src/helm_orchestration/resume_service.py
    - apps/worker/src/helm_worker/jobs/workflow_runs.py
    - tests/unit/test_workflow_orchestration_service.py
    - tests/unit/test_workflow_repositories.py
key-decisions:
  - "Sync retries and restarts rebuild remaining work by querying persisted sync records scoped to the semantic step lineage, not an in-memory cursor."
  - "Orchestration owns execution order, failure classification, and reconciliation policy while connectors expose only upsert and reconcile contracts."
  - "Uncertain write outcomes stop the step as retryable and must reconcile durable identity before Helm attempts another outbound write."
patterns-established:
  - "Sync execution step: claim persisted records in deterministic order, persist each outcome immediately, and stop on retryable or terminal failure."
  - "Connector stubs stay import-safe for storage packages by deferring orchestration schema imports until method execution."
requirements-completed: [SYNC-04, SYNC-05, SYNC-06, RCVR-01, RCVR-02]
duration: 17 min
completed: 2026-03-12
---

# Phase 3 Plan 02: Adapter Writes And Recovery Guarantees Summary

**Idempotent sync execution with reconciliation-first retries, package-layer task/calendar adapters, and restart-safe worker resume**

## Performance

- **Duration:** 17 min
- **Started:** 2026-03-12T22:24:14Z
- **Completed:** 2026-03-12T22:41:04Z
- **Tasks:** 3
- **Files modified:** 14

## Accomplishments
- Added durable sync attempt metadata plus repository queries that select unresolved work by run and semantic step lineage instead of transient progress counters.
- Implemented orchestration-owned sync execution that dispatches task writes before calendar writes, persists every outcome immediately, and reconciles uncertain results before retry.
- Wired resume and worker execution to rebuild remaining sync work from persisted records so retries and post-restart resumes skip completed items and only process unresolved work.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add durable sync execution states and claim-or-update repository flows** - `850a369` (feat)
2. **Task 2: Execute approved sync records through adapters with reconciliation before retry** - `32e4680` (feat)
3. **Task 3: Make resume and worker execution rebuild state from persisted sync facts** - `23c08d1` (feat)

**Additional fix:** `b6f7656` (fix)

## Files Created/Modified
- `migrations/versions/20260313_0011_workflow_sync_execution.py` - Adds sync attempt metadata columns needed for durable retry and resume inspection.
- `packages/storage/src/helm_storage/repositories/workflow_sync_records.py` - Implements step-attempt scoped unresolved queries plus attempt-start, success, and failure helpers.
- `packages/orchestration/src/helm_orchestration/workflow_service.py` - Executes approved sync manifests through adapters with reconciliation-first recovery and run completion semantics.
- `packages/orchestration/src/helm_orchestration/resume_service.py` - Routes sync execution resumes back through orchestration-owned persisted recovery logic.
- `apps/worker/src/helm_worker/jobs/workflow_runs.py` - Wires default sync adapters so worker restarts can resume approved sync steps.
- `tests/unit/test_workflow_orchestration_service.py` - Covers deterministic ordering, retryable stop behavior, reconciliation-first resume, and restart-safe retry semantics.
- `tests/unit/test_workflow_repositories.py` - Covers durable sync attempt metadata and unresolved selection across step attempts.

## Decisions Made
- Used `attempt_count` and `last_attempt_step_id` on sync records so recovery decisions are inspectable without overwriting the original sync identity.
- Kept task and calendar execution inside `packages/connectors` stubs while preserving orchestration ownership of sequencing, retryability, and record mutation.
- Treated reconciliation-required outcomes as retryable step failures so later retries or resumes must prove provider state before issuing another write.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Broke connector/import cycle introduced by new adapter stubs**
- **Found during:** Final verification after Task 3
- **Issue:** Exporting the new sync adapter stubs from `helm_connectors.__init__` pulled in the orchestration package during storage repository import, causing test collection to fail with a circular import.
- **Fix:** Deferred orchestration schema imports inside the stub adapter methods so the connector package remains import-safe at module load time.
- **Files modified:** `packages/connectors/src/helm_connectors/task_system.py`, `packages/connectors/src/helm_connectors/calendar_system.py`
- **Verification:** `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py` and `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py`
- **Committed in:** `b6f7656`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The fix was required for correctness of package imports. No scope creep beyond making the planned adapter boundary viable.

## Issues Encountered
- The plan referenced `migrations/versions/20260313_0010_workflow_sync_execution.py`, but the repository already had `20260313_0010_workflow_sync_records.py`. The execution metadata landed in a follow-on migration `20260313_0011_workflow_sync_execution.py` instead.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Approved sync execution now preserves partial lineage, avoids duplicate writes across retry and resume, and gives later phases a concrete adapter boundary to replace with real integrations.
- Worker and orchestration semantics are aligned around persisted sync facts, so later provider integrations can focus on real API behavior rather than recovery control flow.

## Self-Check: PASSED

---
*Phase: 03-adapter-writes-and-recovery-guarantees*
*Completed: 2026-03-12*
