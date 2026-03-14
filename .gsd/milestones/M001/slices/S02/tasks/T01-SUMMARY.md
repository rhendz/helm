---
id: T01
parent: S02
milestone: M001
provides:
  - durable specialist invocation records linked to workflow runs, steps, and artifacts
  - typed TaskAgent and CalendarAgent dispatch contracts keyed by workflow semantics
  - persisted schedule proposal artifacts with lineage and restart-safe worker resumption
requires: []
affects: []
key_files: []
key_decisions: []
patterns_established: []
observability_surfaces: []
drill_down_paths: []
duration: 6 min
verification_result: passed
completed_at: 2026-03-13
blocker_discovered: false
---
# T01: 02-specialist-dispatch-and-approval-semantics 01

**# Phase 2 Plan 01: Specialist Dispatch And Approval Semantics Summary**

## What Happened

# Phase 2 Plan 01: Specialist Dispatch And Approval Semantics Summary

**Typed TaskAgent and CalendarAgent kernel dispatch with durable invocation lineage and persisted schedule proposal artifacts**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-13T09:41:55Z
- **Completed:** 2026-03-13T09:48:12Z
- **Tasks:** 3
- **Files modified:** 15

## Accomplishments
- Added a dedicated `workflow_specialist_invocations` storage contract and migration, with explicit input/output artifact linkage and execution status.
- Introduced typed TaskAgent and CalendarAgent payload schemas plus workflow-semantic specialist registration inside the orchestration kernel.
- Wired the worker to resume the representative weekly scheduling specialist flow end to end, with restart-safe coverage from raw request through schedule proposal.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add durable specialist invocation persistence and schedule proposal artifact support** - `cb7890a` (feat)
2. **Task 2: Define typed specialist contracts and kernel dispatch semantics** - `e80def1` (feat)
3. **Task 3: Wire worker execution and add representative scheduling-flow coverage** - `64a4264` (feat)

**Plan metadata:** Included in the final docs/state commit for this plan.

## Files Created/Modified
- `migrations/versions/20260313_0008_specialist_dispatch.py` - adds the durable specialist invocation table.
- `packages/storage/src/helm_storage/models.py` - models workflow specialist invocations and artifact relationships.
- `packages/storage/src/helm_storage/repositories/contracts.py` - extends workflow artifact types and specialist invocation repository contracts.
- `packages/storage/src/helm_storage/repositories/workflow_specialist_invocations.py` - stores and updates invocation lineage records.
- `packages/orchestration/src/helm_orchestration/schemas.py` - defines typed TaskAgent, CalendarAgent, and schedule proposal payloads.
- `packages/orchestration/src/helm_orchestration/contracts.py` - defines semantic specialist step registration and execution error contracts.
- `packages/orchestration/src/helm_orchestration/workflow_service.py` - executes specialist steps inside kernel-owned validation and persistence semantics.
- `packages/orchestration/src/helm_orchestration/resume_service.py` - resolves specialist handlers by `(workflow_type, step_name)` and resumes durable state.
- `apps/worker/src/helm_worker/jobs/workflow_runs.py` - registers the representative weekly scheduling specialist steps for worker execution.
- `tests/unit/test_workflow_orchestration_service.py` - verifies task-to-calendar specialist execution, warnings, validation blocking, and restart-safe resumption.
- `tests/unit/test_workflow_repositories.py` - verifies schedule proposal lineage and specialist invocation persistence.
- `tests/unit/test_worker_registry.py` - verifies worker registry wiring for semantic specialist handlers.

## Decisions Made

- Used a dedicated specialist invocation table because approval and operator inspection need direct query access to step execution lineage later.
- Kept validation in the same kernel completion path for both normalized tasks and schedule proposals so approval phases can rely on one durable step history model.
- Registered the representative flow in worker wiring with semantic keys rather than free-form step names to avoid cross-workflow handler collisions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Renamed repository tests so the plan's specialist-only pytest selector matched real coverage**
- **Found during:** Task 1 (Add durable specialist invocation persistence and schedule proposal artifact support)
- **Issue:** `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py -k specialist` deselected every test because the new storage tests did not include `specialist` in their names.
- **Fix:** Renamed the relevant repository tests to carry the `specialist` selector while keeping the storage assertions unchanged.
- **Files modified:** `tests/unit/test_workflow_repositories.py`
- **Verification:** `uv run --frozen --extra dev pytest tests/unit/test_workflow_repositories.py -k specialist`
- **Committed in:** `cb7890a` (part of task commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The deviation only aligned test naming with the plan's required verification command. No scope creep.

## Issues Encountered

- Parallel `git add` calls raced on `.git/index.lock`; switching back to single-command staging preserved atomic commits without touching unrelated planning files.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Approval request storage and operator decision semantics can build directly on top of the new invocation lineage, typed payloads, and schedule proposal artifacts.
- The representative weekly scheduling flow now reaches a persisted proposal artifact without downstream side effects, which is the right checkpoint for Phase 2 plan 02.

## Self-Check

PASSED

- Found summary file on disk.
- Verified task commits `cb7890a`, `e80def1`, and `64a4264` in git history.

---
*Phase: 02-specialist-dispatch-and-approval-semantics*
*Completed: 2026-03-13*
