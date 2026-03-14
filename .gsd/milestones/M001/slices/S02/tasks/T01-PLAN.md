# T01: 02-specialist-dispatch-and-approval-semantics 01

**Slice:** S02 — **Milestone:** M001

## Description

Implement kernel-owned specialist dispatch for `TaskAgent` and `CalendarAgent`, including durable invocation records and schedule proposal persistence.

Purpose: Phase 2 starts by turning the Phase 1 workflow state machine into a typed specialist execution kernel that can drive the representative scheduling flow without yet introducing human approval or downstream writes.
Output: Specialist payload schemas, durable invocation persistence, typed dispatch registration, worker integration, and tests proving request-to-task-to-schedule progression.

## Must-Haves

- [ ] "Helm invokes `TaskAgent` and `CalendarAgent` through one typed kernel dispatch contract instead of ad hoc worker wiring."
- [ ] "Each specialist execution writes a durable invocation record with input reference, output reference, timing, and result status."
- [ ] "The representative scheduling flow can convert raw request input into normalized task artifacts, then convert validated tasks into a persisted schedule proposal artifact."
- [ ] "Specialist execution remains inside kernel-owned workflow step semantics so later approval and sync phases can build on the same step history."

## Files

- `migrations/versions/20260313_0008_specialist_dispatch.py`
- `packages/storage/src/helm_storage/models.py`
- `packages/storage/src/helm_storage/repositories/contracts.py`
- `packages/storage/src/helm_storage/repositories/workflow_artifacts.py`
- `packages/storage/src/helm_storage/repositories/workflow_steps.py`
- `packages/storage/src/helm_storage/repositories/__init__.py`
- `packages/orchestration/src/helm_orchestration/contracts.py`
- `packages/orchestration/src/helm_orchestration/schemas.py`
- `packages/orchestration/src/helm_orchestration/workflow_service.py`
- `packages/orchestration/src/helm_orchestration/resume_service.py`
- `apps/worker/src/helm_worker/jobs/registry.py`
- `apps/worker/src/helm_worker/jobs/workflow_runs.py`
- `tests/unit/test_workflow_orchestration_service.py`
- `tests/unit/test_workflow_repositories.py`
