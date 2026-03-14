# T02: 02-specialist-dispatch-and-approval-semantics 02

**Slice:** S02 — **Milestone:** M001

## Description

Implement first-class approval checkpoints, operator decisions, and approval-driven resume semantics for schedule proposals.

Purpose: Phase 2 requires valid proposal artifacts to pause for human decision before any later side-effect phase can act on them. This plan turns approval into a durable kernel state with shared API and Telegram operator paths.
Output: Approval storage/contracts, checkpoint creation and decision handling, shared read-model updates, API routes, Telegram commands, and tests for approve/reject/revision resume behavior.

## Must-Haves

- [ ] "Helm pauses on a valid schedule proposal before any downstream create, update, or delete action."
- [ ] "Approval checkpoints are durable workflow state, not ephemeral Telegram messages or read-model placeholders."
- [ ] "An operator can approve, reject, or request revision through shared kernel semantics, and the workflow resumes from the correct persisted step boundary."
- [ ] "API and Telegram surfaces expose the same checkpoint state, allowed actions, and last decision outcome from one read model."

## Files

- `migrations/versions/20260313_0009_approval_checkpoints.py`
- `packages/storage/src/helm_storage/models.py`
- `packages/storage/src/helm_storage/repositories/contracts.py`
- `packages/storage/src/helm_storage/repositories/workflow_artifacts.py`
- `packages/storage/src/helm_storage/repositories/workflow_runs.py`
- `packages/storage/src/helm_storage/repositories/workflow_events.py`
- `packages/orchestration/src/helm_orchestration/schemas.py`
- `packages/orchestration/src/helm_orchestration/workflow_service.py`
- `packages/orchestration/src/helm_orchestration/resume_service.py`
- `apps/api/src/helm_api/schemas.py`
- `apps/api/src/helm_api/routers/workflow_runs.py`
- `apps/api/src/helm_api/services/workflow_status_service.py`
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py`
- `apps/telegram-bot/src/helm_telegram_bot/commands/approve.py`
- `tests/unit/test_workflow_orchestration_service.py`
- `tests/unit/test_workflow_status_service.py`
- `tests/unit/test_telegram_commands.py`
- `tests/integration/test_workflow_status_routes.py`
