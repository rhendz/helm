---
phase: 04-representative-scheduling-workflow
plan: 01
subsystem: workflow
tags: [telegram, api, orchestration, scheduling, approval]

requires:
  - phase: 03-adapter-writes-and-recovery-guarantees
    provides: durable sync planning, replay, and approval-gated apply semantics
provides:
  - shared weekly scheduling request contract across Telegram and API
  - deterministic request-driven task normalization and schedule proposal generation
  - compact representative proposal projections for API and Telegram approval flows
affects: [phase-04-plan-02, workflow-status, telegram-commands]

tech-stack:
  added: []
  patterns:
    - shared request parsing before persistence
    - schedule proposal payloads carry explicit constraints, assumptions, rationale, and carry-forward items

key-files:
  created:
    - .planning/phases/04-representative-scheduling-workflow/04-01-SUMMARY.md
  modified:
    - apps/api/src/helm_api/services/workflow_status_service.py
    - apps/worker/src/helm_worker/jobs/workflow_runs.py
    - apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py
    - packages/orchestration/src/helm_orchestration/schemas.py
    - tests/unit/test_workflow_orchestration_service.py

key-decisions:
  - "Keep weekly scheduling request parsing deterministic and shared in the API status service so Telegram and API store the same durable contract."
  - "Extend the shared schedule proposal schema with honored constraints, assumptions, carry-forward tasks, and rationale instead of hiding representative details inside free-form text."
  - "Keep Telegram as a thin formatter over the shared status projection rather than introducing a representative-only read model."

patterns-established:
  - "Representative create flows normalize request text into metadata.weekly_request before the raw request artifact is persisted."
  - "Schedule proposals remain the only source of downstream sync planning while still exposing carry-forward and assumption detail for approval."

requirements-completed: [DEMO-01, DEMO-04, DEMO-05, DEMO-06]
duration: 1h 55m
completed: 2026-03-13
---

# Phase 4: Representative Scheduling Workflow Summary

**Weekly scheduling now starts from a shared Telegram/API request contract, produces deterministic normalized tasks and proposal artifacts, and surfaces approval-ready schedule details without demo-only paths.**

## Performance

- **Duration:** 1h 55m
- **Started:** 2026-03-13T00:15:15Z
- **Completed:** 2026-03-13T02:09:38Z
- **Tasks:** 3
- **Files modified:** 11

## Accomplishments
- Replaced the old Telegram `weekly_digest` default with a shared `weekly_scheduling` create contract and parsed weekly-request metadata.
- Replaced placeholder task and calendar specialist outputs with deterministic normalization, scheduling, carry-forward tracking, and revision-aware proposal generation.
- Extended the shared workflow status projection and Telegram formatter so approval and revision views show scheduled blocks, constraints, assumptions, carry-forward work, and downstream change previews.

## Task Commits

Each task was committed atomically where feasible:

1. **Task 1-3: Representative weekly scheduling implementation and shared projections** - `3fbbfe5`
2. **Plan metadata and summary updates** - pending commit

## Files Created/Modified
- `apps/api/src/helm_api/services/workflow_status_service.py` - Shared weekly-request parsing, create-path normalization, and richer workflow status projection.
- `apps/api/src/helm_api/schemas.py` - API request/response schema defaults and representative proposal fields.
- `apps/worker/src/helm_worker/jobs/workflow_runs.py` - Deterministic weekly task normalization and schedule proposal generation.
- `packages/orchestration/src/helm_orchestration/schemas.py` - Durable weekly request and richer schedule proposal contracts.
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py` - Compact representative proposal formatting in Telegram.
- `tests/unit/test_workflow_orchestration_service.py` - End-to-end representative worker and revision coverage.
- `tests/unit/test_workflow_status_service.py` - Shared create/status projection assertions for weekly scheduling.
- `tests/unit/test_telegram_commands.py` - Telegram proposal formatting coverage for representative details.
- `tests/integration/test_workflow_status_routes.py` - API create route and proposal/revision coverage for the shared weekly scheduling contract.

## Decisions Made
- Shared request parsing lives in the API workflow status service and is reused by Telegram start.
- Weekly requests stay permissive: missing task details create warnings and assumptions instead of rejecting the run.
- Proposal artifacts now carry explicit approval-facing detail fields so Telegram and API can project the same representative view.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Registered calendar specialist step was still missing its persisted post-approval step**
- **Found during:** Task 2 (Replace placeholder specialist handlers with request-driven normalization and proposal generation)
- **Issue:** The worker registry still registered `dispatch_calendar_agent` without `next_step_name="apply_schedule"`, which prevented approval checkpoint creation.
- **Fix:** Updated the worker specialist registration to persist `apply_schedule` as the resumed step after approval.
- **Files modified:** `apps/worker/src/helm_worker/jobs/workflow_runs.py`
- **Verification:** Representative orchestration tests now reach the approval checkpoint and resume path successfully.
- **Committed in:** `3fbbfe5`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Required for correctness. No scope expansion.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
Plan `04-02` can focus on deeper completion-lineage and restart/recovery verification. The representative create, proposal, approval, and revision loop is now running on the shared kernel contract.

---
*Phase: 04-representative-scheduling-workflow*
*Completed: 2026-03-13*
