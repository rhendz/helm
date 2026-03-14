# T03: 02-specialist-dispatch-and-approval-semantics 03

**Slice:** S02 — **Milestone:** M001

## Description

Implement revision-driven proposal versioning and operator-visible decision lineage for approval-driven rework.

Purpose: Phase 2 is incomplete if a revision request only edits the current proposal in place. This plan makes proposal rework durable and inspectable by version so approval history survives later retries, resumes, and downstream sync phases.
Output: Revision payload contracts, proposal-version lineage behavior, latest-first read-model updates, API and Telegram version inspection, runbook notes, and tests for supersession and version-specific decisions.

## Must-Haves

- [ ] "A revision request creates a new proposal version inside the same workflow run rather than overwriting or forking the run."
- [ ] "Each proposal version preserves lineage to the superseded version and to the revision feedback that produced it."
- [ ] "Approval or rejection decisions always resolve a specific proposal version, and operator views can show which version is latest, approved, rejected, or superseded."
- [ ] "Revision is distinct from retry: revision re-enters the proposal-producing specialist step with feedback, while retry re-attempts the same failed step."

## Files

- `packages/storage/src/helm_storage/repositories/contracts.py`
- `packages/storage/src/helm_storage/repositories/workflow_artifacts.py`
- `packages/storage/src/helm_storage/repositories/workflow_events.py`
- `packages/orchestration/src/helm_orchestration/schemas.py`
- `packages/orchestration/src/helm_orchestration/workflow_service.py`
- `packages/orchestration/src/helm_orchestration/resume_service.py`
- `apps/api/src/helm_api/schemas.py`
- `apps/api/src/helm_api/services/workflow_status_service.py`
- `apps/api/src/helm_api/routers/workflow_runs.py`
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py`
- `apps/telegram-bot/src/helm_telegram_bot/commands/approve.py`
- `docs/runbooks/workflow-runs.md`
- `tests/unit/test_workflow_orchestration_service.py`
- `tests/unit/test_workflow_status_service.py`
- `tests/unit/test_telegram_commands.py`
- `tests/integration/test_workflow_status_routes.py`
