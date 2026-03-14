---
id: T02
parent: S01
milestone: M001
provides:
  - Typed workflow request, artifact, validation, and failure schemas.
  - Durable orchestration services for validation gating, retry, terminate, and resume semantics.
  - Worker polling entrypoint for storage-backed workflow resume handling.
requires: []
affects: []
key_files: []
key_decisions: []
patterns_established: []
observability_surfaces: []
drill_down_paths: []
duration: 6min
verification_result: passed
completed_at: 2026-03-13
blocker_discovered: false
---
# T02: 01-durable-workflow-foundation 02

**# Phase 1 Plan 2: Typed Orchestration Summary**

## What Happened

# Phase 1 Plan 2: Typed Orchestration Summary

**Typed workflow validation, durable blocked and failed run transitions, and storage-backed worker resume polling for the orchestration kernel**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-13T07:40:56Z
- **Completed:** 2026-03-13T07:50:38Z
- **Tasks:** 3
- **Files modified:** 11

## Accomplishments

- Added typed workflow request, artifact, validation-report, execution-failure, and final-summary schemas with a validator registry keyed by step name or artifact type.
- Built orchestration services that create runs, persist candidate artifacts, block on validation failures, persist ordinary execution failures, and support explicit retry and terminate actions.
- Added a worker workflow polling job plus service-level tests showing blocked runs stay non-runnable until retry and completed runs emit final summary artifacts.

## Task Commits

Each task was committed atomically:

1. **Task 1: Define typed workflow schemas and validation outcomes** - `3c9e256` (feat)
2. **Task 2: Implement orchestration services for run creation, step transitions, and blocked validation failures** - `84f8f43` (feat)
3. **Task 3: Add worker resume entrypoint, blocked-run action handling, and execution notes** - `ede0410` (feat)

Post-task auto-fix:

- `e22bdde` (fix): guard workflow worker without handlers

## Files Created/Modified

- `packages/orchestration/src/helm_orchestration/contracts.py` - validator targeting and step execution result contracts.
- `packages/orchestration/src/helm_orchestration/schemas.py` - typed workflow request, artifact, validation, failure, and summary schemas.
- `packages/orchestration/src/helm_orchestration/validators.py` - validator registry plus normalized-task validation logic.
- `packages/orchestration/src/helm_orchestration/workflow_service.py` - durable run creation, step transitions, validation gating, retry, terminate, and final-summary helpers.
- `packages/orchestration/src/helm_orchestration/resume_service.py` - restart-safe runnable-run resume flow with durable failure handling for missing or failing handlers.
- `apps/worker/src/helm_worker/jobs/workflow_runs.py` - worker entrypoint that polls runnable workflow runs from storage.
- `tests/unit/test_workflow_orchestration_service.py` - validation, blocked-run, failure, retry, terminate, resume, and final-summary coverage.

## Decisions Made

- Used Pydantic models for orchestration payloads so validation and storage serialization stay explicit and machine-readable.
- Requeued retries by creating a new pending step attempt on the same run instead of mutating the failed attempt in place.
- Treated missing worker step handlers as persisted execution failures because the plan requires adapter-free execution errors to remain inspectable.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Prevented the new workflow worker job from failing runs when no handlers are configured**
- **Found during:** Final verification after Task 3
- **Issue:** The newly added `workflow_runs` job instantiated `WorkflowResumeService` with an empty handler map, which would convert any runnable workflow into a durable `missing_step_handler` failure instead of safely waiting for later specialist wiring.
- **Fix:** Guarded the job so it skips polling until handlers are registered, added an injectable resume-service builder for testability, and covered both the safe skip path and the injected resume path in unit tests.
- **Files modified:** `apps/worker/src/helm_worker/jobs/workflow_runs.py`, `tests/unit/test_worker_registry.py`, `packages/orchestration/README.md`
- **Verification:** `uv run --frozen --extra dev pytest tests/unit/test_workflow_orchestration_service.py tests/unit/test_worker_registry.py`
- **Committed in:** `e22bdde`

---

**Total deviations:** 1 auto-fixed (Rule 1: bug)
**Impact on plan:** The fix preserves the intended durable semantics of Task 3 without changing plan scope or storage contracts.

## Issues Encountered

- The sandbox blocked `.git/index.lock` creation during staging, so git staging and commit commands were rerun with elevated permissions.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 2 can plug specialist step handlers into the new resume service and reuse the typed artifact and failure contracts.
- API and Telegram read paths can now expose blocked, failed, retryable, and validation-artifact state from durable records instead of transient worker memory.

## Self-Check

PASSED
