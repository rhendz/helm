# T01: 01-durable-workflow-foundation 01

**Slice:** S01 — **Milestone:** M001

## Description

Establish the durable Postgres persistence layer for workflow runs, step attempts, artifacts, and transition history.

Purpose: Create the kernel-owned workflow vocabulary and storage contracts that later orchestration and operator surfaces can rely on without reusing email-specific tables.
Output: Migration, ORM models, repository contracts, repository implementations, and repository tests for workflow foundation entities.

## Must-Haves

- [ ] "A workflow request survives process restart because its run identity, current step, and status are durably stored in Postgres."
- [ ] "An operator-facing status surface can later reconstruct what happened last from persisted step attempts, artifacts, and run state alone."
- [ ] "Each workflow run preserves inspectable lineage from raw request through validation and final summary artifacts without relying on prompt memory."

## Files

- `migrations/versions/20260313_0007_workflow_foundation.py`
- `packages/storage/src/helm_storage/models.py`
- `packages/storage/src/helm_storage/repositories/contracts.py`
- `packages/storage/src/helm_storage/repositories/workflow_runs.py`
- `packages/storage/src/helm_storage/repositories/workflow_steps.py`
- `packages/storage/src/helm_storage/repositories/workflow_artifacts.py`
- `packages/storage/src/helm_storage/repositories/workflow_events.py`
- `packages/storage/src/helm_storage/repositories/__init__.py`
- `tests/unit/test_workflow_repositories.py`
