---
estimated_steps: 4
estimated_files: 1
---

# T02: Unit tests for inline execution, approval, and worker recovery

**Slice:** S03 — Immediate execution path for operator actions
**Milestone:** M004

## Description

Create `tests/unit/test_task_execution.py` with unit tests proving the three execution paths wired in T01 work correctly: (1) inline `/task` advances run state to `blocked`/`needs_action` via `complete_current_step`, (2) `/approve` triggers inline `resume_run` for `apply_schedule`, (3) worker `_build_specialist_steps` includes the `task_quick_add` handler. Also covers error and edge cases: `PastEventError` in schedule block construction, `complete_current_step` failure, and `None` inference result.

Uses the same test stub pattern as `tests/unit/test_task_command.py` — `_Message`, `_Update`, `_Context` helper classes. All tests are pure unit tests: mock the `TelegramWorkflowStatusService` methods, verify the Telegram handler's behavior (what messages are pushed, what methods are called).

**Relevant skills:** `test` skill for test generation patterns.

## Steps

1. **Create `tests/unit/test_task_execution.py`** with test stubs and helper classes. Import `task` and `approve` command modules, `_build_specialist_steps` from `workflow_runs`, and relevant schema types. Reuse the `_Message`/`_Update`/`_Application`/`_Context` stub pattern from `test_task_command.py`.

2. **Write tests for the `/task` inline execution path** (tests exercise `_run_task_async`):
   - `test_task_inline_execution_pushes_approval_notification`: Mock `LLMClient.infer_task_semantics` to return fixed `TaskSemantics`. Mock `_service.execute_task_run` to return a dict with `needs_action=True` and an `active_approval_checkpoint` containing `target_artifact_id=42`. Run `_run_task_async`. Assert the pushed message contains "Schedule proposal ready", the run_id, artifact_id 42, and "/approve".
   - `test_task_inline_execution_success_notification`: Mock `execute_task_run` returning `needs_action=False`, status `completed`. Assert success notification pushed (not approval request).
   - `test_task_inline_execution_error_pushes_message`: Mock `execute_task_run` raising `RuntimeError`. Assert error message pushed with run_id and "❌".
   - `test_task_past_event_error_pushes_user_message`: Mock `execute_task_run` raising `PastEventError`. Assert message mentions "past" or similar user-friendly text.
   - `test_task_inference_returns_none_pushes_error`: Mock `LLMClient.infer_task_semantics` returning `None`. Assert error message pushed.

3. **Write tests for the `/approve` inline execution path**:
   - `test_approve_triggers_inline_execution_after_approval`: Mock `_workflow_service.approve_run` returning a valid result dict. Mock `_workflow_service.execute_after_approval` returning success. Call `approve.handle` with args `["1", "42"]`. Assert both `approve_run` and `execute_after_approval` were called, and a success message was pushed.
   - `test_approve_inline_execution_failure_still_confirms_approval`: Mock `execute_after_approval` raising. Assert approval is still confirmed to user (approval itself succeeded), with a graceful fallback message about calendar sync completing shortly.

4. **Write tests for worker recovery handler registration**:
   - `test_build_specialist_steps_includes_task_quick_add`: Call `_build_specialist_steps()` and assert `("task_quick_add", "infer_task_semantics")` is in the returned dict.
   - `test_task_quick_add_step_handler_produces_schedule_proposal`: Get the step handler from `_build_specialist_steps()`, verify its `artifact_type` is `WorkflowArtifactKind.SCHEDULE_PROPOSAL` and `next_step_name` is `"apply_schedule"`.

## Must-Haves

- [ ] At least 7 tests covering: approval notification, success notification, error handling, PastEventError, None inference, approve inline execution, worker handler registration
- [ ] All tests use mock/stub pattern — no real DB, no real LLM calls, no network
- [ ] Tests import from the actual production modules (not copied code)
- [ ] All existing tests still pass (no regressions)

## Verification

- `pytest tests/unit/test_task_execution.py -v` — all tests pass
- `pytest tests/unit/ -v` — no regressions in existing unit tests
- `pytest tests/integration/ -v` — no regressions in integration tests

## Inputs

- `apps/telegram-bot/src/helm_telegram_bot/commands/task.py` — T01's rewritten `_run_task_async` (the function under test)
- `apps/telegram-bot/src/helm_telegram_bot/commands/approve.py` — T01's updated approve handler
- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — T01's extended `_build_specialist_steps()`
- `tests/unit/test_task_command.py` — pattern reference for `_Message`/`_Update`/`_Context` stubs
- S01 summary: `TaskSemantics` model fields (urgency, priority, sizing_minutes, confidence); `_run_task_async` wraps entire body in try/except for PTB silent drop protection
- T01 expected output: `execute_task_run` and `execute_after_approval` methods on `TelegramWorkflowStatusService`; `_run_task_async` calls `execute_task_run` then checks `needs_action`; `approve.handle` calls `execute_after_approval` after `approve_run`

## Expected Output

- `tests/unit/test_task_execution.py` — 9+ tests covering all execution paths, error cases, and worker recovery; all passing

## Observability Impact

**Signals changed by this task:** None — this is a pure test file. No new runtime signals are added.

**How a future agent inspects this task:**
- Run `uv run --frozen --extra dev pytest tests/unit/test_task_execution.py -v` to see all 10 tests and their pass/fail state.
- Each test directly exercises a specific runtime code path (e.g., `_run_task_async`, `approve.handle`, `_build_specialist_steps`) via monkeypatching — so if production code regresses, specific tests fail with clear names pointing to the broken path.
- The structlog signals (`task_execution_complete`, `task_execution_failed`, `task_execution_past_time`, `approve_inline_execution_failed`) from T01 remain the runtime observability surface; these tests verify the *code paths* that emit those signals.

**Failure visibility:**
- If `test_run_task_async_needs_action_sends_approval_notification` fails: the approval notification message no longer contains run_id + artifact_id + `/approve` hint — operator won't know how to approve.
- If `test_approve_inline_execution_failure_still_confirms_approval` fails: approve fallback path broken — operator could get no reply on inline execution error.
- If `test_build_specialist_steps_includes_task_quick_add` fails: worker recovery won't pick up orphaned `task_quick_add` runs from the polling loop.
- If `test_task_quick_add_step_handler_produces_schedule_proposal` fails: the recovery step would produce wrong artifact type or advance to the wrong next step, breaking the approval checkpoint chain.

**Redaction constraints:** No secrets in test data — all fixtures use hardcoded IDs and strings.
