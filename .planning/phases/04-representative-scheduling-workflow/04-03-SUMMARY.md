---
phase: 04-representative-scheduling-workflow
plan: 03
subsystem: workflow-status
tags: [api, telegram, replay, recovery, representative-workflow]

requires:
  - phase: 04-representative-scheduling-workflow
    provides: representative final-summary lineage plus shared completion and recovery projections
provides:
  - replay-aware representative completion summaries that prefer live recovery state over stale success copy
  - completed-then-replayed regression coverage across shared status, replay lineage, and Telegram formatting
  - documented closure for the phase 4 replay recovery summary gap
affects: [workflow-status, replay-service, telegram-commands]

tech-stack:
  added: []
  patterns:
    - shared operator projections prefer live recovery-class state over historical final-summary outcome text
    - final-summary artifacts remain durable lineage records even when operator-facing replay status changes later

key-files:
  created:
    - .planning/phases/04-representative-scheduling-workflow/04-03-SUMMARY.md
  modified:
    - apps/api/src/helm_api/services/workflow_status_service.py
    - tests/unit/test_replay_service.py
    - tests/unit/test_workflow_status_service.py
    - tests/unit/test_telegram_commands.py
    - .planning/STATE.md
    - .planning/ROADMAP.md

key-decisions:
  - "Replay-requested recovery classification now overrides stale final-summary success in the shared completion projection."
  - "Representative final-summary artifacts stay unchanged after replay so lineage remains inspectable while live status turns recovery-oriented."
  - "Telegram /workflows continues to format the shared completion summary instead of adding surface-specific replay semantics."

patterns-established:
  - "When replay is active, completion_summary.downstream_sync_status mirrors live recovery_class rather than persisted final_summary.downstream_sync_status."
  - "Completed-then-replayed representative runs keep completed status and final-summary lineage, but operator messaging points to downstream follow-up."

requirements-completed: [DEMO-06]
duration: 23 min
completed: 2026-03-13
---

# Phase 4: Representative Scheduling Workflow Summary

**Completed representative runs that later enter replay now project truthful recovery-oriented follow-up across API and Telegram without rewriting final-summary lineage.**

## Performance

- **Duration:** 23 min
- **Started:** 2026-03-13T22:45:00Z
- **Completed:** 2026-03-13T23:08:13Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments
- Fixed the shared representative completion projection so live `replay_requested` recovery wins over stale persisted success messaging.
- Added narrow regressions for completed-then-replayed runs in shared status and replay lineage coverage.
- Proved Telegram `/workflows` keeps rendering the shared replay-aware projection rather than diverging with bot-only status logic.

## Task Commits

Each task was committed atomically where feasible:

1. **Tasks 1-3: Shared replay-aware status projection and focused regression coverage** - `e26eeb5`
2. **Plan metadata: summary and planning state updates** - `PENDING`

## Files Created/Modified
- `apps/api/src/helm_api/services/workflow_status_service.py` - Live downstream sync status helper plus replay-first completion headline and attention precedence.
- `tests/unit/test_workflow_status_service.py` - Regression for completed representative runs that later become replay-requested.
- `tests/unit/test_replay_service.py` - Replay lineage coverage proving completed runs retain durable recovery signals after replay request.
- `tests/unit/test_telegram_commands.py` - `/workflows` formatting coverage for completed-but-replay-requested representative runs.
- `.planning/phases/04-representative-scheduling-workflow/04-03-SUMMARY.md` - This execution summary.
- `.planning/STATE.md` - Project completion metadata updated for plan 04-03.
- `.planning/ROADMAP.md` - Phase 4 plan count and gap-closure completion updated.

## Decisions Made
- Let the shared status projection, not Telegram formatting, decide when replay-recovery overrides stale completion copy.
- Keep `lineage.final_summary.downstream_sync_status` as the historical persisted value while `completion_summary.downstream_sync_status` reflects live recovery truth.
- Scope regressions tightly to the completed-then-replayed representative path instead of widening the whole workflow matrix.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- The initial replay-service regression attempted to drive completed sync execution through an orchestration service without adapters configured.
- Resolved by adding a local completed-run helper with hermetic success adapters and asserting on the replay lineage path directly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
Phase 4 gap closure is complete. Representative runs now keep their completion lineage while operator-facing summaries truthfully switch to replay follow-up when downstream recovery is active.

---
*Phase: 04-representative-scheduling-workflow*
*Completed: 2026-03-13*
