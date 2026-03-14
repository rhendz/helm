# T02: 01-durable-workflow-foundation 02

**Slice:** S01 — **Milestone:** M001

## Description

Implement the typed orchestration and validation boundary that turns persisted workflow records into a durable, restart-safe workflow state machine.

Purpose: Phase 1 is not complete with storage alone; the kernel must own step advancement, validation failure blocking, and persisted failure/retryability semantics before later phases add approvals or side effects.
Output: Typed workflow schemas, validation services, orchestration services, worker polling/resume entrypoint, and service-level tests for success and blocked-state transitions.

## Must-Haves

- [ ] "Workflow step execution only advances after typed artifact validation passes or passes with warnings."
- [ ] "Malformed, incomplete, or materially ambiguous specialist output moves the step into `validation_failed` and the run into a durable blocked state."
- [ ] "Blocked validation-failure runs require an explicit persisted retry or terminate action before any downstream step can continue."
- [ ] "An ordinary step-execution exception or adapter-free execution error marks the step and run as failed durably, with the failed step, error summary, and retryability state persisted even when no validation artifact is produced."
- [ ] "Failure details and retryability are stored durably so worker restart can resume, retry, or terminate from the correct persisted step boundary."

## Files

- `packages/orchestration/src/helm_orchestration/__init__.py`
- `packages/orchestration/src/helm_orchestration/contracts.py`
- `packages/orchestration/src/helm_orchestration/schemas.py`
- `packages/orchestration/src/helm_orchestration/validators.py`
- `packages/orchestration/src/helm_orchestration/workflow_service.py`
- `packages/orchestration/src/helm_orchestration/resume_service.py`
- `apps/worker/src/helm_worker/jobs/registry.py`
- `apps/worker/src/helm_worker/jobs/workflow_runs.py`
- `packages/orchestration/README.md`
- `tests/unit/test_workflow_orchestration_service.py`
