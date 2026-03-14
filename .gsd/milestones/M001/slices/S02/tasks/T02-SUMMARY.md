---
id: T02
parent: S02
milestone: M001
provides:
  - durable approval checkpoint persistence tied to schedule proposal artifacts
  - kernel-owned approve, reject, and revision decision handling with automatic resume
  - shared API and Telegram approval projections and operator actions
requires: []
affects: []
key_files: []
key_decisions: []
patterns_established: []
observability_surfaces: []
drill_down_paths: []
duration: 9min
verification_result: passed
completed_at: 2026-03-13
blocker_discovered: false
---
# T02: 02-specialist-dispatch-and-approval-semantics 02

**# Phase 2 Plan 02: Approval Semantics Summary**

## What Happened

# Phase 2 Plan 02: Approval Semantics Summary

**Durable schedule approval checkpoints with shared approve/reject/revision semantics across the kernel, API, and Telegram**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-13T09:56:53Z
- **Completed:** 2026-03-13T10:05:59Z
- **Tasks:** 3
- **Files modified:** 23

## Accomplishments
- Added durable approval checkpoint storage with allowed actions, decision metadata, revision feedback, and explicit resume pointers.
- Taught the orchestration kernel to block on schedule proposals, then approve, reject, or request revision without a second manual resume action.
- Exposed one checkpoint-aware workflow status model through API routes and Telegram commands for inspection and decision submission.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add durable approval checkpoint and decision persistence** - `cc7f4fd` (feat)
2. **Task 2: Implement checkpoint creation, operator decision handling, and resume semantics in the kernel** - `749c4c0` (feat)
3. **Task 3: Expose approval checkpoints through shared API and Telegram operator paths** - `368894d` (feat)

**Plan metadata:** pending

## Files Created/Modified
- `migrations/versions/20260313_0009_approval_checkpoints.py` - Adds approval checkpoint persistence and run resume metadata columns.
- `packages/storage/src/helm_storage/models.py` - Defines approval checkpoint ORM relationships on runs and artifacts.
- `packages/storage/src/helm_storage/repositories/workflow_approval_checkpoints.py` - Implements checkpoint CRUD and active-checkpoint lookup.
- `packages/orchestration/src/helm_orchestration/schemas.py` - Defines typed approval actions, request, and decision payloads.
- `packages/orchestration/src/helm_orchestration/workflow_service.py` - Creates approval checkpoints from schedule proposals and resolves approve/reject/revision outcomes.
- `apps/api/src/helm_api/services/workflow_status_service.py` - Projects checkpoint status, proposal summary, and last decision into the shared read model.
- `apps/api/src/helm_api/routers/workflow_runs.py` - Adds approval, rejection, and revision HTTP routes.
- `apps/telegram-bot/src/helm_telegram_bot/commands/approve.py` - Adds Telegram approve, reject, and request-revision command entrypoints.
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py` - Renders approval context and actions in Telegram workflow listings.
- `tests/unit/test_workflow_orchestration_service.py` - Verifies approval pause, approve-to-resume, reject-to-close, and revision-to-regenerate behavior.

## Decisions Made

- Used a dedicated checkpoint table plus approval request/decision artifacts so run state answers both “what is pending now?” and “what resolved it later?”
- Distinguished approval-blocked state with `blocked_reason=approval_required` so status surfaces do not confuse approval waits with validation or execution failures.
- Resumed approved runs by moving them back to `pending` on the next persisted step boundary, which keeps worker polling simple and restart-safe.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- SQLAlchemy identity-map reuse caused one orchestration test to observe the later resumed state on an earlier object reference; the test was tightened to capture the intermediate step boundary explicitly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 3 can now attach downstream adapter writes behind the approval gate without inventing new operator semantics.
- Proposal revision still regenerates from the proposal-producing step using persisted feedback; Phase 02-03 can deepen version lineage and supersession detail on top of this contract.

## Self-Check

PASSED

---
*Phase: 02-specialist-dispatch-and-approval-semantics*
*Completed: 2026-03-13*
