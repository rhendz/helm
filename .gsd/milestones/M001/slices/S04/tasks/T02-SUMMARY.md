---
id: T02
parent: S04
milestone: M001
provides:
  - representative final-summary artifacts with approval and sync lineage
  - outcome-first completion and recovery summaries on shared API and Telegram surfaces
  - representative verification for completion, replay, and restart-safe resume
requires: []
affects: []
key_files: []
key_decisions: []
patterns_established: []
observability_surfaces: []
drill_down_paths: []
duration: 55 min
verification_result: passed
completed_at: 2026-03-13
blocker_discovered: false
---
# T02: 04-representative-scheduling-workflow 02

**# Phase 4: Representative Scheduling Workflow Summary**

## What Happened

# Phase 4: Representative Scheduling Workflow Summary

**Representative completed runs now carry approval-to-sync lineage in their final summary artifact and expose compact, truthful completion or recovery summaries across API and Telegram.**

## Performance

- **Duration:** 55 min
- **Started:** 2026-03-13T02:10:00Z
- **Completed:** 2026-03-13T03:05:00Z
- **Tasks:** 3
- **Files modified:** 11

## Accomplishments
- Auto-populated representative final summaries with approval decision linkage, sync record ids, and downstream reference ids from durable kernel state.
- Added shared completion and recovery summaries that foreground scheduled outcome, sync status, and carry-forward attention items without hiding inspectable lineage.
- Expanded representative verification and runbook notes for approved writes, replay/recovery projection, and restart-safe resume around approval and `apply_schedule`.

## Task Commits

Each task was committed atomically where feasible:

1. **Task 1-2: Representative lineage and shared completion summaries** - `dceede5`
2. **Task 3: Representative verification, runbook, and planning artifacts** - `329c1e1`

## Files Created/Modified
- `packages/orchestration/src/helm_orchestration/workflow_service.py` - Final summary lineage assembly and auto-persisted representative completion summaries.
- `apps/api/src/helm_api/services/workflow_status_service.py` - Shared completion/recovery projection derived from persisted final summaries and sync state.
- `apps/api/src/helm_api/schemas.py` - Typed completion summary response contract.
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py` - Compact Telegram outcome formatting for representative completion and recovery states.
- `tests/unit/test_workflow_orchestration_service.py` - Coverage for persisted approval and sync lineage in representative final summaries.
- `tests/unit/test_workflow_status_service.py` - Coverage for queued, completed, and recovery summary projections.
- `tests/unit/test_telegram_commands.py` - Coverage for compact representative completion formatting.
- `tests/unit/test_replay_service.py` - Recovery-summary coverage for replay-requested representative runs.
- `tests/integration/test_workflow_status_routes.py` - End-to-end route coverage for representative completed final-summary lineage.
- `docs/runbooks/workflow-runs.md` - Manual verification steps for create, revision, approval, completion, and restart-safe resume.

## Decisions Made
- Auto-create representative final summary artifacts at sync completion so completed runs do not rely on out-of-band summary insertion.
- Treat sync record ids as the durable downstream lineage ids in the final summary contract, with human-facing reference ids derived from persisted external object ids or planned item keys.
- Prefer a shared `completion_summary` projection for operator-facing messaging and leave deep lineage in `lineage.final_summary` and proposal history.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Replay-requested runs were summarized as merely queued**
- **Found during:** Task 2 (Tighten representative completion and recovery summaries on shared operator surfaces)
- **Issue:** The shared completion headline treated replay-requested runs as ordinary queued work, which understated that downstream follow-up was already required.
- **Fix:** Updated the shared completion headline logic to treat any persisted recovery classification as downstream follow-up.
- **Files modified:** `apps/api/src/helm_api/services/workflow_status_service.py`, `tests/unit/test_replay_service.py`
- **Verification:** `tests/unit/test_replay_service.py` passes with replay-requested runs reporting the recovery headline.
- **Committed in:** `dceede5`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Required for truthful recovery messaging. No scope expansion.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
Phase 4 is complete. The representative weekly scheduling workflow now proves request capture, proposal revision, approval gating, approved writes, recovery projection, and final lineage through the shared kernel surfaces.

---
*Phase: 04-representative-scheduling-workflow*
*Completed: 2026-03-13*
