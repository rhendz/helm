---
phase: 03-adapter-writes-and-recovery-guarantees
plan: 04
subsystem: api
tags: [workflow-status, api, telegram, recovery-projection, sync-lineage]
requires:
  - phase: 03-adapter-writes-and-recovery-guarantees
    provides: durable sync records, recovery classification, replay lineage, partial termination snapshots
provides:
  - shared workflow status projection for approved-write effect summaries and durable sync counts
  - recovery-aware operator hints derived from sync rows instead of workflow event text
  - replay lineage metadata that later API and Telegram entrypoints can consume directly
affects: [api, telegram-bot, workflow-status-projection]
tech-stack:
  added: []
  patterns: [shared durable status projection, sync-first operator summaries, replay metadata projection]
key-files:
  created: [.planning/phases/03-adapter-writes-and-recovery-guarantees/03-04-SUMMARY.md]
  modified: [apps/api/src/helm_api/services/workflow_status_service.py, tests/unit/test_workflow_status_service.py]
key-decisions:
  - "Workflow status projection reads sync counts, recovery class, and replay lineage directly from workflow_sync_records so operator surfaces do not parse workflow events."
  - "Effect summaries stay compact and stable: total writes plus task/calendar counts before execution begins."
  - "Terminal partial-sync state takes precedence over stale adapter error text when projecting operator-facing recovery summaries."
patterns-established:
  - "API and Telegram consumers receive one explicit sync projection with counts, last unresolved item, replay lineage, and safe-next-action hints."
  - "Recovery precedence comes from durable sync classifications before step-level failure text."
requirements-completed: [OPER-01]
duration: 9 min
completed: 2026-03-12
---

# Phase 3 Plan 4: Workflow Status Projection Summary

**Shared workflow status projection for approved write counts, durable sync recovery summaries, and replay lineage metadata**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-12T22:56:00Z
- **Completed:** 2026-03-12T23:04:55Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments
- Added an effect summary to the shared workflow status service so operator surfaces can show pending approved task and calendar writes before execution starts.
- Projected sync counts by state and target, last failed or unresolved item metadata, recovery class, and safe-next-action hints from durable sync rows.
- Locked the contract with status-service tests covering recoverable failure, terminal failure, terminated partial sync, and replay lineage after termination.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend the shared workflow status projection with effect and recovery summaries** - `886ee08` (feat)
2. **Task 2: Project partial-sync and termination outcomes without raw-event inspection** - `cb4d839` (feat)
3. **Task 3: Lock the status projection contract before app-layer entrypoints consume it** - `a28d5be` (feat)

## Files Created/Modified
- `apps/api/src/helm_api/services/workflow_status_service.py` - Projects effect summaries, sync counts, recovery class, replay lineage, and safe-next-action hints from durable sync rows.
- `tests/unit/test_workflow_status_service.py` - Verifies the shared projection contract for pending effects, recoverable failure, terminal failure, partial termination, and replay-after-termination lineage.

## Decisions Made
- The shared projection now treats `workflow_sync_records` as the source of truth for operator recovery state, keeping API and Telegram entrypoints thin.
- Compact effect summaries were limited to total writes plus task/calendar splits so the default operator view stays concise.
- When partial sync has already been terminated, the projection reports the durable terminal recovery state instead of surfacing the earlier adapter timeout as the primary summary.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected failure-summary precedence for terminated partial sync**
- **Found during:** Task 2 (Project partial-sync and termination outcomes without raw-event inspection)
- **Issue:** The new projection still surfaced the previous adapter timeout after termination instead of the durable `terminated_after_partial_success` recovery state.
- **Fix:** Updated sync failure-summary precedence and retryability projection so terminated partial-sync runs report the terminal recovery snapshot as the authoritative outcome.
- **Files modified:** `apps/api/src/helm_api/services/workflow_status_service.py`
- **Verification:** `uv run --frozen --extra dev pytest tests/unit/test_workflow_status_service.py -k 'partial or terminal or lineage'`
- **Committed in:** `a28d5be`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The fix stayed within the shared projection boundary and was required to keep operator recovery semantics correct.

## Issues Encountered
- Parallel `git add` calls briefly contended on `.git/index.lock`; staging was switched back to sequential git operations for the remaining task commits.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- API and Telegram entrypoints can now consume one durable status projection for effect summaries, sync recovery state, and replay lineage.
- Plan `03-05` can wire operator-facing surfaces on top of this contract without re-implementing recovery rules.

## Self-Check
PASSED
- Found `.planning/phases/03-adapter-writes-and-recovery-guarantees/03-04-SUMMARY.md`
- Verified commits `886ee08`, `cb4d839`, and `a28d5be` exist in git history

---
*Phase: 03-adapter-writes-and-recovery-guarantees*
*Completed: 2026-03-12*
