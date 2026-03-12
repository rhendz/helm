---
phase: 03-adapter-writes-and-recovery-guarantees
plan: 01
subsystem: database
tags: [sqlalchemy, adapters, sync-records, orchestration, idempotency]
requires:
  - phase: 02-specialist-dispatch-and-approval-semantics
    provides: approved proposal artifacts and approval decision lineage
provides:
  - durable workflow sync records anchored to approved proposal artifact ids and versions
  - task-system and calendar-system adapter contracts with normalized sync request and outcome schemas
  - orchestration-owned sync manifest preparation before any outbound write execution
affects: [phase-03-recovery, phase-04-representative-scheduling, workflow-status]
tech-stack:
  added: []
  patterns: [durable sync manifest, adapter-owned side effects, proposal-version anchored idempotency]
key-files:
  created:
    - migrations/versions/20260313_0010_workflow_sync_records.py
    - packages/storage/src/helm_storage/repositories/workflow_sync_records.py
  modified:
    - packages/storage/src/helm_storage/models.py
    - packages/storage/src/helm_storage/repositories/contracts.py
    - packages/storage/src/helm_storage/repositories/workflow_events.py
    - packages/orchestration/src/helm_orchestration/contracts.py
    - packages/orchestration/src/helm_orchestration/schemas.py
    - packages/orchestration/src/helm_orchestration/workflow_service.py
    - tests/unit/test_workflow_repositories.py
    - tests/unit/test_workflow_orchestration_service.py
key-decisions:
  - "Approved proposal execution now materializes deterministic task and calendar sync records before any adapter call path runs."
  - "Sync identity is anchored to proposal artifact id, proposal version, target system, sync kind, and planned item key with relational uniqueness."
  - "Adapter protocols return normalized request, outcome, and reconciliation envelopes while orchestration retains ordering and retry policy."
patterns-established:
  - "Approved sync manifests are persisted through storage repositories and inspected through workflow events, not inferred from transient execution state."
  - "Task and calendar side effects must cross explicit adapter contracts owned by the orchestration boundary."
requirements-completed: [SYNC-01, SYNC-02, SYNC-03]
duration: 20 min
completed: 2026-03-12
---

# Phase 03 Plan 01: Durable Approved Sync Manifest Summary

**Approved proposal versions now expand into deterministic task and calendar sync records with durable lineage, explicit adapter contracts, and inspectable manifest-creation events**

## Performance

- **Duration:** 20 min
- **Started:** 2026-03-12T22:02:53Z
- **Completed:** 2026-03-12T22:22:53Z
- **Tasks:** 3
- **Files modified:** 11

## Accomplishments
- Added a durable `workflow_sync_records` table, ORM model, repository contracts, and SQLAlchemy implementation for outbound write manifests.
- Added provider-neutral task and calendar adapter protocols plus normalized sync item, request, result, and reconciliation schemas.
- Extended `WorkflowOrchestrationService` so approval of a concrete proposal version prepares stable sync records and logs an inspectable `approved_sync_manifest_created` event before execution continues.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add durable sync-record schema and repository contracts** - `fe80bf9` (feat)
2. **Task 2: Define adapter contracts and sync-item schemas for approved writes** - `7ede056` (feat)
3. **Task 3: Persist approved sync manifests from proposal approval lineage** - `def75be` (feat)

## Files Created/Modified
- `migrations/versions/20260313_0010_workflow_sync_records.py` - Adds durable relational storage for outbound sync manifests with uniqueness and lineage constraints.
- `packages/storage/src/helm_storage/models.py` - Defines `WorkflowSyncRecordORM` and links sync records to runs and steps.
- `packages/storage/src/helm_storage/repositories/contracts.py` - Adds sync repository contracts, patch/query dataclasses, and sync payload typing.
- `packages/storage/src/helm_storage/repositories/workflow_sync_records.py` - Implements sync-record creation, identity lookup, remaining/failed queries, and claim/update operations.
- `packages/orchestration/src/helm_orchestration/contracts.py` - Declares task/calendar adapter protocols and approved sync plan vocabulary.
- `packages/orchestration/src/helm_orchestration/schemas.py` - Adds normalized sync item, request, response, and reconciliation schemas.
- `packages/orchestration/src/helm_orchestration/workflow_service.py` - Prepares approved sync manifests from proposal lineage and records manifest creation events.
- `tests/unit/test_workflow_repositories.py` - Covers sync-record durability, lineage, and remaining/failed query behavior.
- `tests/unit/test_workflow_orchestration_service.py` - Covers adapter schema contracts, approval-driven sync manifest creation, and duplicate preparation safety.

## Decisions Made
- Persist sync state in a dedicated `workflow_sync_records` table rather than hiding write identity inside workflow events or summaries.
- Derive sync manifests from the approved schedule proposal artifact itself so retries and replays have a stable proposal-version anchor.
- Keep retry, reconciliation, and ordering policy in orchestration while adapters only execute normalized task or calendar requests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Shifted the sync migration to revision `20260313_0010`**
- **Found during:** Task 1 (Add durable sync-record schema and repository contracts)
- **Issue:** The plan named `20260313_0009_workflow_sync_records.py`, but `20260313_0009` was already used by the approval checkpoint migration.
- **Fix:** Created the sync migration as `migrations/versions/20260313_0010_workflow_sync_records.py` and kept the rest of the schema work unchanged.
- **Files modified:** `migrations/versions/20260313_0010_workflow_sync_records.py`
- **Verification:** Repository and orchestration tests passed against the new revision.
- **Committed in:** `fe80bf9`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** No scope change. The revision-number adjustment was required to keep Alembic history valid.

## Issues Encountered
- Parallel `git add` commands contended on `.git/index.lock`, so staging reverted to sequential `git add` calls for the remaining task commits.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 03 now has a durable sync-plan layer and adapter vocabulary ready for idempotency, reconciliation, and resume-safe execution work.
- Replay semantics, retry-safe duplicate prevention across actual adapter execution, and operator-facing recovery summaries remain for later Phase 03 plans.

## Self-Check: PASSED
- Found summary file: `.planning/phases/03-adapter-writes-and-recovery-guarantees/03-01-SUMMARY.md`
- Found task commits: `fe80bf9`, `7ede056`, `def75be`
