---
phase: 01-durable-workflow-foundation
plan: 02
subsystem: orchestration
tags: [pydantic, sqlalchemy, worker, workflow, validation]
requires:
  - phase: 01-01
    provides: Durable workflow run, step, artifact, and event persistence tables and repositories.
provides:
  - Typed workflow request, artifact, validation, and failure schemas.
  - Durable orchestration services for validation gating, retry, terminate, and resume semantics.
  - Worker polling entrypoint for storage-backed workflow resume handling.
affects: [phase-02-specialist-dispatch, api-read-paths, telegram-run-status]
tech-stack:
  added: []
  patterns: [Pydantic artifact contracts, storage-backed workflow state machine, worker resume polling]
key-files:
  created:
    - packages/orchestration/src/helm_orchestration/contracts.py
    - packages/orchestration/src/helm_orchestration/schemas.py
    - packages/orchestration/src/helm_orchestration/validators.py
    - packages/orchestration/src/helm_orchestration/workflow_service.py
    - packages/orchestration/src/helm_orchestration/resume_service.py
    - apps/worker/src/helm_worker/jobs/workflow_runs.py
    - tests/unit/test_workflow_orchestration_service.py
  modified:
    - packages/orchestration/src/helm_orchestration/__init__.py
    - apps/worker/src/helm_worker/jobs/registry.py
    - packages/orchestration/README.md
    - tests/unit/test_worker_registry.py
key-decisions:
  - "Model workflow artifacts and failures as explicit Pydantic schemas so storage payloads stay typed before specialist adapters exist."
  - "Treat validation failures as blocked runs that require an explicit retry or terminate action instead of implicit worker progression."
  - "Fail runnable steps durably when no step handler exists so adapter-free execution errors are visible in persisted state."
patterns-established:
  - "WorkflowOrchestrationService owns step-state transitions, artifact persistence, and validation gating over storage repositories."
  - "WorkflowResumeService derives runnable work from persisted run state and delegates actual step execution through named handlers."
requirements-completed: [FLOW-03, FLOW-04, AGNT-04, AGNT-05, AGNT-06, ARTF-03, ARTF-05]
duration: 6min
completed: 2026-03-13
---

# Phase 1 Plan 2: Typed Orchestration Summary

**Typed workflow validation, durable blocked and failed run transitions, and storage-backed worker resume polling for the orchestration kernel**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-13T07:40:56Z
- **Completed:** 2026-03-13T07:47:03Z
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

None - plan executed exactly as written.

## Issues Encountered

- The sandbox blocked `.git/index.lock` creation during staging, so git staging and commit commands were rerun with elevated permissions.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 2 can plug specialist step handlers into the new resume service and reuse the typed artifact and failure contracts.
- API and Telegram read paths can now expose blocked, failed, retryable, and validation-artifact state from durable records instead of transient worker memory.

## Self-Check

PASSED
