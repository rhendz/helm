# T03: 01-durable-workflow-foundation 03

**Slice:** S01 — **Milestone:** M001

## Description

Expose durable workflow ingest and inspection through API and Telegram-friendly operator paths so users can start, inspect, and recover workflow runs without raw database access.

Purpose: The Phase 1 goal requires an explicit request-ingest path plus inspectable run status and lineage, not just persisted records. This plan turns the new kernel state into operator-facing API and Telegram flows for creation, triage, and recovery.
Output: Workflow run API schemas/routes/services, Telegram status service and commands, and route/read-model tests for start, status, lineage, and recovery visibility.

## Must-Haves

- [ ] "An operator can start a workflow run from a new request through an existing Helm surface and receive the created run ID, initial status, and current step without querying storage directly."
- [ ] "An operator can inspect workflow run status, current step, latest outcome, and needs-action state without querying the database directly."
- [ ] "API detail views expose lineage across raw request, step transitions, validation outcomes, artifacts, and final state for a single workflow run."
- [ ] "Telegram-friendly workflow summaries stay concise while still showing what run this is, what happened last, whether action is required, and whether retry or terminate is the next recovery action."
- [ ] "Operator-facing read models distinguish ordinary execution failures from blocked validation failures, expose an explicit `paused_state` plus nullable `pause_reason`, and expose the final summary contract even when approval or downstream sync linkages are still null."

## Files

- `apps/api/src/helm_api/schemas.py`
- `apps/api/src/helm_api/routers/workflow_runs.py`
- `apps/api/src/helm_api/services/workflow_status_service.py`
- `apps/api/src/helm_api/main.py`
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py`
- `apps/telegram-bot/src/helm_telegram_bot/main.py`
- `docs/runbooks/workflow-runs.md`
- `tests/unit/test_workflow_status_service.py`
- `tests/integration/test_workflow_status_routes.py`
