---
id: T03
parent: S01
milestone: M001
provides:
  - Shared workflow run triage read model with explicit paused-state semantics
  - API endpoints for workflow run create, inspect, retry, and terminate actions
  - Telegram commands for workflow start, summary, needs-action review, and recovery
requires: []
affects: []
key_files: []
key_decisions: []
patterns_established: []
observability_surfaces: []
drill_down_paths: []
duration: 12min
verification_result: passed
completed_at: 2026-03-13
blocker_discovered: false
---
# T03: 01-durable-workflow-foundation 03

**# Phase 1 Plan 3: Durable Workflow Operator Surfaces Summary**

## What Happened

# Phase 1 Plan 3: Durable Workflow Operator Surfaces Summary

**Workflow run ingest, triage, lineage inspection, and recovery actions exposed through FastAPI and Telegram using a shared durable read model**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-13T07:52:00Z
- **Completed:** 2026-03-13T08:04:16Z
- **Tasks:** 3
- **Files modified:** 11

## Accomplishments

- Built a shared workflow status projection that answers the operator triage question directly from durable run, step, artifact, and event records.
- Added API routes for workflow run creation, filtered listing, detailed lineage inspection, retry, and terminate actions.
- Added Telegram commands for workflow start, recent summaries, needs-action summaries, and explicit retry and terminate recovery flows.

## Task Commits

1. **Task 1: Build a single workflow status read model for operator triage** - `8eec956` (feat)
2. **Task 2: Add API ingest, inspection, and blocked-run action routes backed by the workflow read model** - `0f56cf2` (feat)
3. **Task 3: Add Telegram-friendly workflow start, summary, and blocked-run recovery commands** - `9526c14` (feat)

## Files Created/Modified

- `apps/api/src/helm_api/services/workflow_status_service.py` - Shared projection for workflow run summaries, details, lineage, and recovery actions.
- `apps/api/src/helm_api/routers/workflow_runs.py` - Workflow run create/list/detail/retry/terminate endpoints.
- `apps/api/src/helm_api/schemas.py` - Workflow run request and response schemas for summary, detail, lineage, and final summary contracts.
- `apps/api/src/helm_api/main.py` - Registered the workflow run router.
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py` - Thin Telegram wrapper around the shared workflow read model.
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py` - Telegram workflow operator commands and concise triage formatting.
- `apps/telegram-bot/src/helm_telegram_bot/main.py` - Registered workflow Telegram commands.
- `docs/runbooks/workflow-runs.md` - Manual verification notes for API and Telegram workflow create, inspect, retry, and terminate flows.
- `tests/unit/test_workflow_status_service.py` - Read-model coverage for blocked, failed, completed, and lineage cases.
- `tests/integration/test_workflow_status_routes.py` - API coverage for create, empty list, running, blocked, retried, terminated, failed, and completed routes.
- `tests/unit/test_telegram_commands.py` - Telegram workflow command coverage.

## Decisions Made

- Shared the operator-facing workflow projection in one service so the API and Telegram surfaces cannot silently diverge on paused-state or recovery semantics.
- Returned explicit `available_actions` from the read model so clients can render retry and terminate affordances without reconstructing workflow rules.
- Kept final summary linkage keys present even before approval and downstream sync phases populate them, which locks the Phase 1 contract early.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Integration tests needed a `StaticPool` SQLite engine with `check_same_thread=False` because FastAPI `TestClient` runs endpoint work on a different thread than fixture setup.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 1 now exposes operator-visible workflow ingest, inspect, and recovery surfaces with durable lineage.
- Phase 2 can build specialist execution and richer workflow progression on top of the stable read-model and final-summary contracts introduced here.

## Self-Check: PASSED

- Summary file exists.
- Task commits `8eec956`, `0f56cf2`, and `9526c14` exist in git history.

---
*Phase: 01-durable-workflow-foundation*
*Completed: 2026-03-13*
