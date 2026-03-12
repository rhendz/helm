---
phase: 02-specialist-dispatch-and-approval-semantics
plan: 03
subsystem: workflow
tags: [postgres, fastapi, telegram, pydantic, workflow-lineage]
requires:
  - phase: 02-01
    provides: typed specialist execution and invocation persistence
  - phase: 02-02
    provides: approval checkpoints, decision artifacts, and pause/resume semantics
provides:
  - Revision-linked schedule proposal versions inside a single workflow run
  - Version-aware API and Telegram status projections for proposal lineage
  - Version-targeted approval, rejection, and revision actions
affects: [phase-03-adapter-writes, phase-04-representative-scheduling, operator-status]
tech-stack:
  added: []
  patterns: [artifact lineage via supersedes_artifact_id, latest-first proposal projections, version-targeted approval actions]
key-files:
  created: []
  modified:
    - packages/orchestration/src/helm_orchestration/workflow_service.py
    - apps/api/src/helm_api/services/workflow_status_service.py
    - apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py
    - tests/unit/test_workflow_orchestration_service.py
    - docs/runbooks/workflow-runs.md
key-decisions:
  - "Approval decisions now require the concrete proposal artifact id so operator actions cannot silently resolve against an implied latest version."
  - "Revision requests create a dedicated revision_request artifact and the next schedule_proposal supersedes the prior proposal while staying in the same workflow run."
patterns-established:
  - "Proposal version lineage: revision feedback is stored as an artifact, and the next proposal links to both the revision request and the superseded proposal."
  - "Operator read-models stay latest-first by default but preserve explicit proposal history for inspection and downstream linkage."
requirements-completed: [APRV-05, APRV-06, ARTF-04]
duration: 15min
completed: 2026-03-12
---

# Phase 2 Plan 03: Proposal Versioning Summary

**Revision-linked schedule proposal versions with latest-first operator views and version-targeted approval decisions**

## Performance

- **Duration:** 15 min
- **Started:** 2026-03-12T10:05:00Z
- **Completed:** 2026-03-12T10:19:54Z
- **Tasks:** 3
- **Files modified:** 17

## Accomplishments
- Persisted revision requests as first-class workflow artifacts and linked new schedule proposals to the superseded version they replace.
- Added latest-first proposal version projections for API and Telegram so operators can inspect superseded, approved, and rejected versions.
- Required approval, rejection, and revision actions to target a concrete proposal artifact id and documented manual verification steps.

## Task Commits

1. **Task 1: Implement revision-linked proposal version creation in the kernel and repositories** - `ec95d53` (feat)
2. **Task 2: Make workflow status and operator routes version-aware** - `2077fa4` (feat)
3. **Task 3: Add revision/versioning tests and runbook verification notes** - `57aeee3` (test)

## Files Created/Modified
- `packages/storage/src/helm_storage/repositories/contracts.py` - Added revision-request and version-aware approval payload contracts.
- `packages/storage/src/helm_storage/repositories/workflow_artifacts.py` - Added artifact-type queries used to reconstruct proposal lineage.
- `packages/orchestration/src/helm_orchestration/workflow_service.py` - Created revision-linked proposal versions and enforced version-targeted decisions.
- `apps/api/src/helm_api/services/workflow_status_service.py` - Built latest-first proposal history projections and proposal-version detail output.
- `apps/api/src/helm_api/routers/workflow_runs.py` - Added proposal-version route and concrete artifact targeting for approval actions.
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py` - Added compact latest-version rendering and `/workflow_versions`.
- `apps/telegram-bot/src/helm_telegram_bot/commands/approve.py` - Required proposal artifact ids for approve, reject, and revision commands.
- `tests/unit/test_workflow_orchestration_service.py` - Covered revision-linked proposal supersession.
- `tests/unit/test_workflow_status_service.py` - Covered version-aware status projection and decision lineage.
- `tests/unit/test_telegram_commands.py` - Covered concrete-target Telegram approval and version inspection flows.
- `tests/integration/test_workflow_status_routes.py` - Covered version-aware API routes and version-targeted approval requests.
- `docs/runbooks/workflow-runs.md` - Added manual verification steps for revision, supersession, and approved-version inspection.

## Decisions Made
- Approval, rejection, and revision submissions now name the `target_artifact_id` explicitly to prevent accidental resolution against a later proposal version.
- Proposal lineage stays in `workflow_artifacts` using `lineage_parent_id` and `supersedes_artifact_id` instead of introducing a parallel revision store.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Incremented repeated approval-step attempts inside one run**
- **Found during:** Task 1 (Implement revision-linked proposal version creation in the kernel and repositories)
- **Issue:** A second revision cycle tried to recreate `await_schedule_approval` with attempt `1`, violating the unique step-attempt constraint.
- **Fix:** Compute the next persisted attempt number before creating a new approval checkpoint step.
- **Files modified:** `packages/orchestration/src/helm_orchestration/workflow_service.py`
- **Verification:** `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py -k revision`
- **Committed in:** `ec95d53`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The auto-fix was required for multi-revision correctness and stayed within the planned workflow versioning scope.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 3 can now attach downstream task/calendar writes to the exact approved proposal artifact instead of an ambiguous latest proposal.
- The representative scheduling flow in Phase 4 can expose revision history without adding a separate revision store.

## Self-Check
PASSED
