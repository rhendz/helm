# S03: Immediate execution path for operator actions

**Goal:** `/task` and `/approve` complete within seconds using the corrected scheduling primitives from S02; polling loop retained only for background recovery of orphaned runnable steps.
**Demo:** Operator sends `/task book dentist tomorrow at 2pm` → ack within 1s → seconds later: "⏳ Schedule proposal ready (run N, artifact M) — /approve N M to confirm" → operator sends `/approve N M` → workflow advances to `apply_schedule` immediately (no 30s wait).

## Must-Haves

- `/task` background coroutine calls `WorkflowOrchestrationService.complete_current_step()` after inference, producing a `SCHEDULE_PROPOSAL` artifact that auto-creates an approval checkpoint
- Approval notification pushed to operator when `run.needs_action=True` with run ID, artifact ID, and proposal summary
- `/approve <run_id> <artifact_id>` triggers inline `resume_run()` to execute `apply_schedule` immediately after approval
- `task_quick_add` step handler registered in `_build_specialist_steps()` for worker recovery of orphaned runs
- `past_event_guard` called before building `ScheduleBlock` in the task execution path
- Error handling: all inline execution wrapped in try/except with user-facing error push

## Proof Level

- This slice proves: integration (Telegram handler → orchestration service → DB state transitions → notification)
- Real runtime required: no (DB-backed integration tests with mocked Calendar adapter)
- Human/UAT required: no (manual smoke test recommended but not blocking)

## Verification

- `pytest tests/unit/test_task_execution.py -v` — new test file covering:
  - Inline execution after inference produces `SCHEDULE_PROPOSAL` artifact and sets `needs_action=True`
  - Approval notification message contains run ID, artifact ID, and `/approve` hint
  - `/approve` triggers inline `resume_run` after approval submission
  - Worker recovery picks up orphaned `task_quick_add` run via `_build_specialist_steps`
  - `past_event_guard` rejects past-time task with user-facing error
  - Error in `complete_current_step` produces user-facing error push (not silent failure)
- `pytest tests/unit/test_task_command.py -v` — existing tests still pass (no regressions)
- `pytest tests/unit/test_task_inference.py -v` — existing tests still pass
- `pytest tests/unit/ -v && pytest tests/integration/ -v` — full suite green

## Observability / Diagnostics

- Runtime signals: structlog `task_execution_complete` with run_id/status/needs_action; structlog `task_execution_failed` on error; existing `task_inference_complete` from S01
- Inspection surfaces: `workflow_runs` table: `task_quick_add` runs transition from `pending` → `blocked` (needs_action=True) after `/task`; then `pending` → `completed` after `/approve`
- Failure visibility: error message pushed to operator Telegram chat with run ID; structlog exception trace; `run.execution_error_summary` in DB
- Redaction constraints: none (no secrets in scheduling data)

## Integration Closure

- Upstream surfaces consumed:
  - `packages/orchestration/src/helm_orchestration/scheduling.py` — `compute_reference_week`, `parse_local_slot`, `to_utc`, `past_event_guard`, `PastEventError`, `ConditionalApprovalPolicy`
  - `packages/orchestration/src/helm_orchestration/workflow_service.py` — `WorkflowOrchestrationService.complete_current_step()`, `execute_specialist_step()`, `submit_approval_decision()`
  - `packages/orchestration/src/helm_orchestration/resume_service.py` — `WorkflowResumeService.resume_run()`
  - `packages/orchestration/src/helm_orchestration/schemas.py` — `CalendarAgentOutput`, `ScheduleBlock`, `TaskSemantics`
  - `apps/telegram-bot/src/helm_telegram_bot/commands/task.py` — `_run_task_async` (S01 stub to replace)
  - `apps/worker/src/helm_worker/jobs/workflow_runs.py` — `_build_specialist_steps()`, `_build_resume_service()`
- New wiring introduced in this slice:
  - `TelegramWorkflowStatusService.execute_task_run(run_id)` — builds orchestration service + calls `complete_current_step`
  - `TelegramWorkflowStatusService.execute_after_approval(run_id)` — builds resume service + calls `resume_run`
  - `_build_task_quick_add_step()` in `workflow_runs.py` — worker recovery handler
  - Updated `approve.py` — inline execution after approval
- What remains before the milestone is truly usable end-to-end: S04 (Telegram UX), S05 (E2E tests), S06 (observability/cleanup)

## Tasks

- [x] **T01: Wire inline execution for /task and /approve with worker recovery** `est:1h`
  - Why: This is the core production code change — replaces the S01 stub (inference + text push) with real orchestration service calls that advance workflow state through approval checkpoint and calendar sync, and wires `/approve` to execute immediately rather than waiting for the 30s polling cycle.
  - Files: `apps/telegram-bot/src/helm_telegram_bot/commands/task.py`, `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`, `apps/telegram-bot/src/helm_telegram_bot/commands/approve.py`, `apps/worker/src/helm_worker/jobs/workflow_runs.py`, `packages/orchestration/src/helm_orchestration/contracts.py`
  - Do: (1) Add `TASK_INFERENCE` to `SpecialistName` enum. (2) Add `execute_task_run(run_id, *, semantics, request_text)` to `TelegramWorkflowStatusService` — opens a session, builds `WorkflowOrchestrationService` (reusing `_build_validator_registry`/`_build_calendar_adapter` from `workflow_runs.py` or inlining equivalent), calls `complete_current_step(run_id, artifact_type=SCHEDULE_PROPOSAL, artifact_payload=CalendarAgentOutput(...), next_step_name="apply_schedule")`, returns the resulting state dict. (3) Add `execute_after_approval(run_id)` to `TelegramWorkflowStatusService` — opens session, builds resume service with task_quick_add handlers, calls `resume_run(run_id)`, returns state. (4) Rewrite `_run_task_async` in `task.py`: keep inference via `run_in_executor`, then build `CalendarAgentOutput` from `TaskSemantics` (single `ScheduleBlock` with `compute_reference_week`/`parse_local_slot`/`to_utc`/`past_event_guard`), call `execute_task_run`, check `needs_action` on result, push approval notification with run_id/artifact_id/`/approve` hint. (5) Update `approve.py`: after `approve_run()`, call `execute_after_approval(run_id)` in a try/except, push result or error. (6) Add `_build_task_quick_add_step()` in `workflow_runs.py` and register it in `_build_specialist_steps()`.
  - Verify: `python -c "from helm_telegram_bot.commands import task; from helm_telegram_bot.commands import approve; print('imports ok')"` and `python -c "from helm_worker.jobs.workflow_runs import _build_specialist_steps; steps = _build_specialist_steps(); assert ('task_quick_add', 'infer_task_semantics') in steps; print('handler registered')"` 
  - Done when: `/task` background coroutine calls `complete_current_step` with a real `CalendarAgentOutput`; `/approve` triggers inline `resume_run`; worker step handler registered for `task_quick_add`

- [ ] **T02: Unit tests for inline execution, approval, and worker recovery** `est:45m`
  - Why: Proves the three execution paths work correctly — inline `/task` advances to blocked state, `/approve` triggers immediate execution, worker recovery picks up orphaned runs — and that error/edge cases produce user-facing feedback.
  - Files: `tests/unit/test_task_execution.py`
  - Do: Create `tests/unit/test_task_execution.py` with tests: (1) `_run_task_async` with mocked `execute_task_run` returning `needs_action=True` → approval notification pushed with run_id, artifact_id, `/approve` hint. (2) `_run_task_async` with mocked `execute_task_run` returning `needs_action=False` → success notification. (3) `_run_task_async` with `execute_task_run` raising → error message pushed. (4) `past_event_guard` raising `PastEventError` during `CalendarAgentOutput` construction → user-facing error. (5) `approve.handle` calls `execute_after_approval` after successful `approve_run`. (6) `_build_specialist_steps()` includes `("task_quick_add", "infer_task_semantics")` key. (7) The step handler for `task_quick_add` produces a `CalendarAgentOutput` from run state. Use the same test stub pattern as `test_task_command.py` (`_Update`, `_Message`, `_Context` classes).
  - Verify: `pytest tests/unit/test_task_execution.py -v` — all tests pass; `pytest tests/unit/ -v && pytest tests/integration/ -v` — no regressions
  - Done when: All 7+ tests pass; full unit + integration suite green

## Files Likely Touched

- `apps/telegram-bot/src/helm_telegram_bot/commands/task.py`
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`
- `apps/telegram-bot/src/helm_telegram_bot/commands/approve.py`
- `apps/worker/src/helm_worker/jobs/workflow_runs.py`
- `packages/orchestration/src/helm_orchestration/contracts.py`
- `tests/unit/test_task_execution.py`
