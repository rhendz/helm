---
estimated_steps: 7
estimated_files: 3
---

# T02: Add/extend integration test for weekly scheduling end-to-end

**Slice:** S03 — Task/calendar workflow protection and verification
**Milestone:** M002

## Description

Introduce or extend an integration test that exercises the representative weekly scheduling / task+calendar workflow through API and worker semantics. The test should create a weekly scheduling workflow run via the API, drive it through schedule proposal, approval, apply_schedule, and sync using existing orchestration/worker wiring, and then assert on key invariants from R003: approval checkpoints, proposal-to-sync linkage, and completion summary semantics. This test becomes a primary automated guardrail for task/calendar workflows after cleanup.

## Steps

1. Inspect existing integration tests under `tests/integration/` (especially workflow status and worker-related tests) to identify current coverage for weekly scheduling and status projections.
2. Decide whether to add a new file `tests/integration/test_weekly_scheduling_end_to_end.py` or extend an existing workflow-focused integration test, based on structure and duplication risk.
3. Design a happy-path test case that uses API routes (and any existing fixtures/helpers) to create a weekly scheduling workflow run with representative input, then advances the workflow through schedule proposal, approval, and apply_schedule, leveraging worker job functions or background job helpers as needed.
4. Within the test, assert on approval checkpoint creation, schedule proposal artifacts, and their linkage to sync records and workflow steps, using repositories or status service projections as appropriate.
5. Add assertions on completion summary fields (e.g., total writes, task/calendar counts, recovery class, safe_next_actions) to ensure the status projection remains consistent with stored sync records.
6. Run `uv run --frozen --extra dev pytest -q tests/integration/test_weekly_scheduling_end_to_end.py` (or the chosen file) and iterate until it passes reliably.
7. Cross-check the test scenario against the UAT script from T01 to ensure both exercise the same representative flow and verify the same core invariants.

## Must-Haves

- [ ] Integration test covers a full weekly scheduling happy path via API + worker semantics (create → proposal → approval → apply_schedule → sync).
- [ ] Test asserts on both kernel-level behavior (approval checkpoints, proposal artifacts, sync records) and operator-facing projections (completion summary fields relevant to weekly scheduling).

## Observability Impact

- **New signals:** Integration test creates explicit pytest coverage for weekly scheduling workflows. Test output directly shows which assertions fail when weekly scheduling behavior regresses.
- **Inspection surfaces:** 
  - Test output via `pytest -v` shows test flow and assertion pass/fail for each workflow state transition.
  - Database queries during test can be inspected via test logs to verify sync records, approval checkpoints, and workflow step creation.
  - Pytest fixtures and test helpers provide programmatic access to workflow state for manual verification if needed.
- **Failure visibility:**
  - Test failure clearly signals a regression in weekly scheduling end-to-end behavior (proposal creation, approval checkpoints, apply_schedule, or sync writes).
  - Assertion failures on completion summary fields immediately show if status projection is out of sync with persisted data.
  - If worker job execution fails, test captures the error state and failure reason.
- **Future inspection:** A future agent can run the test to verify weekly scheduling is functional. If it fails, the test name and assertion message indicate which part of the flow broke.

## Verification

- `uv run --frozen --extra dev pytest -q tests/integration/test_weekly_scheduling_end_to_end.py`
- Confirm that intentionally breaking a key invariant (e.g., changing a completion summary field) causes the test to fail in a way that clearly signals a weekly scheduling regression.

## Inputs

- `tests/integration/test_workflow_status_routes.py`, `tests/integration/test_workflow_status_service.py` — existing integration coverage to align with.
- `apps/api/src/helm_api/services/workflow_status_service.py` — status projection and weekly scheduling helpers used to interpret workflow runs.
- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — worker job wiring for workflow execution and apply_schedule.

## Expected Output

- `tests/integration/test_weekly_scheduling_end_to_end.py` (or equivalent) — an integration test file that exercises weekly scheduling end-to-end and guards core invariants.
- Potential small adjustments to API/worker test fixtures or helpers to support the new test without expanding truth beyond weekly scheduling.