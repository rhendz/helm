---
phase: 02-specialist-dispatch-and-approval-semantics
plan: 02
subsystem: workflow
tags: [approval, telegram, api, postgres, orchestration]
requires:
  - phase: 02-specialist-dispatch-and-approval-semantics
    provides: typed TaskAgent and CalendarAgent dispatch with durable invocation lineage
provides:
  - durable approval checkpoint persistence tied to schedule proposal artifacts
  - kernel-owned approve, reject, and revision decision handling with automatic resume
  - shared API and Telegram approval projections and operator actions
affects: [phase-03-adapter-writes-and-recovery-guarantees, phase-04-representative-scheduling-workflow]
tech-stack:
  added: [SQLAlchemy approval checkpoint persistence]
  patterns: [kernel-owned approval decisions, shared workflow status read model, approval-blocked run state]
key-files:
  created: [.planning/phases/02-specialist-dispatch-and-approval-semantics/02-02-SUMMARY.md, migrations/versions/20260313_0009_approval_checkpoints.py, packages/storage/src/helm_storage/repositories/workflow_approval_checkpoints.py]
  modified: [packages/orchestration/src/helm_orchestration/workflow_service.py, apps/api/src/helm_api/services/workflow_status_service.py, apps/telegram-bot/src/helm_telegram_bot/commands/approve.py]
key-decisions:
  - "Approval checkpoints live in a dedicated workflow_approval_checkpoints table and are linked to approval request and decision artifacts."
  - "Schedule proposals block the run at an explicit await_schedule_approval step instead of completing the workflow or reusing validation-failure semantics."
  - "API and Telegram surfaces consume one checkpoint-aware workflow status projection and delegate all decision semantics back to the orchestration kernel."
patterns-established:
  - "Approval Gate Pattern: valid schedule proposals become blocked runs with allowed actions and a persisted resume pointer."
  - "Operator Thin Surface Pattern: API routes and Telegram commands only parse input, call kernel decisions, and render the shared read model."
requirements-completed: [APRV-01, APRV-02, APRV-03, APRV-04]
duration: 9min
completed: 2026-03-13
---

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
