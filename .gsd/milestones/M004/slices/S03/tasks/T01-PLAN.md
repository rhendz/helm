---
estimated_steps: 6
estimated_files: 5
---

# T01: Wire inline execution for /task and /approve with worker recovery

**Slice:** S03 — Immediate execution path for operator actions
**Milestone:** M004

## Description

Replace the S01 stub in `_run_task_async` (which only infers semantics and pushes text) with real orchestration calls that advance workflow state through the approval checkpoint. Wire `/approve` to execute the `apply_schedule` step immediately after approval rather than waiting for the 30s worker poll. Register a `task_quick_add` step handler in the worker's `_build_specialist_steps()` so orphaned runs are recovered by the polling loop.

The key architectural insight (from research): `WorkflowOrchestrationService.complete_current_step()` with `artifact_type=SCHEDULE_PROPOSAL` auto-creates an approval checkpoint (sets `needs_action=True`, `status=blocked`). No changes needed in `workflow_service.py`. The Telegram handler calls `complete_current_step` after inference, then checks the resulting state and pushes an approval notification.

**Relevant skills:** None specific — this is Python orchestration wiring.

## Steps

1. **Add `TASK_INFERENCE` to `SpecialistName` enum** in `packages/orchestration/src/helm_orchestration/contracts.py`. This is the specialist name for the `task_quick_add` step handler.

2. **Add `execute_task_run()` to `TelegramWorkflowStatusService`** in `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`:
   - Method signature: `execute_task_run(self, run_id: int, *, semantics: TaskSemantics, request_text: str) -> dict[str, object]`
   - Opens a `SessionLocal()` session
   - Builds a `CalendarAgentOutput` from `TaskSemantics`:
     - Import `compute_reference_week`, `parse_local_slot`, `to_utc`, `past_event_guard`, `PastEventError` from `helm_orchestration`
     - Import `RuntimeAppSettings` from `helm_runtime.config` (or read `OPERATOR_TIMEZONE` from `os.environ`)
     - Get `tz = ZoneInfo(settings.operator_timezone)` (construct `RuntimeAppSettings()` or use `os.environ["OPERATOR_TIMEZONE"]` directly)
     - `week_start = compute_reference_week(tz)`
     - `local_start = parse_local_slot(request_text, week_start, tz)` — if None, fall back to `week_start.replace(hour=9)` (next 9am)
     - `start_utc = to_utc(local_start, tz)`
     - `end_utc = start_utc + timedelta(minutes=semantics.sizing_minutes or 60)`
     - `past_event_guard(start_utc, tz)` — raises `PastEventError` if in past
     - Build `ScheduleBlock(title=request_text, task_title=request_text, start=start_utc.isoformat(), end=end_utc.isoformat())`
     - Build `CalendarAgentOutput(proposal_summary=f"Schedule: {request_text}", calendar_id="primary", time_blocks=(block,), proposed_changes=(f"Schedule {request_text}",))`
   - Builds `WorkflowOrchestrationService(session, validator_registry=..., task_system_adapter=StubTaskSystemAdapter(), calendar_system_adapter=_build_calendar_adapter())`
     - For the validator registry: import `_build_validator_registry` from `helm_worker.jobs.workflow_runs` OR duplicate the minimal version needed (just `ScheduleProposalValidator` for the `SCHEDULE_PROPOSAL` artifact type)
     - For `_build_calendar_adapter`: import from `helm_worker.jobs.workflow_runs` OR duplicate
     - **Preferred**: import both from `workflow_runs.py` to avoid duplication. These are pure factory functions with no side effects.
   - Calls `wf_service.complete_current_step(run_id, artifact_type=WorkflowArtifactType.SCHEDULE_PROPOSAL.value, artifact_payload=output, next_step_name="apply_schedule")`
   - Returns `WorkflowStatusService(session).get_run_detail(run_id)` (the dict summary)

3. **Add `execute_after_approval()` to `TelegramWorkflowStatusService`**:
   - Method signature: `execute_after_approval(self, run_id: int) -> dict[str, object]`
   - Opens a `SessionLocal()` session
   - Builds a `WorkflowResumeService` with both `weekly_scheduling` and `task_quick_add` handlers (import `_build_specialist_steps` and `_build_resume_service` from `workflow_runs.py`)
   - Calls `resume_service.resume_run(run_id)`
   - Returns `WorkflowStatusService(session).get_run_detail(run_id)`

4. **Rewrite `_run_task_async` in `task.py`**:
   - Keep the existing `run_in_executor` inference call
   - Add `None` guard on `semantics` (if `output_parsed` was None)
   - Replace the `_policy.evaluate()` + text formatting with:
     ```python
     result = await loop.run_in_executor(
         None, _service.execute_task_run, run_id,
         # keyword args don't work with run_in_executor — use functools.partial or a lambda
     )
     ```
     Actually: use `functools.partial(_service.execute_task_run, run_id, semantics=semantics, request_text=task_text)` as the callable for `run_in_executor`.
   - Check the resulting state: if `needs_action` is True, format an approval notification:
     ```
     ⏳ Schedule proposal ready (run {run_id})
     {proposal_summary}
     Type /approve {run_id} {artifact_id} to confirm.
     ```
     Extract `artifact_id` from the run detail — look in the result dict for the active approval checkpoint's `target_artifact_id`. The `get_run_detail` result includes `active_approval_checkpoint` with `target_artifact_id`.
   - If `needs_action` is False (completed), push success message
   - Keep the `try/except Exception` wrapping with error push
   - Handle `PastEventError` specifically: push a user-friendly message ("The requested time is in the past…")
   - Remove `_policy` import and module-level `_policy = ConditionalApprovalPolicy()` (policy evaluation now happens via the approval checkpoint flow)

5. **Update `approve.py`** — after the two-arg `/approve <run_id> <artifact_id>` branch:
   - After `result = _workflow_service.approve_run(...)`, add:
     ```python
     # Trigger immediate execution of apply_schedule step
     try:
         _workflow_service.execute_after_approval(run_id)
         await update.message.reply_text("✅ Approved and syncing to calendar…")
     except Exception:
         logger.exception("approve_inline_execution_failed", run_id=run_id)
         await update.message.reply_text(
             f"✅ Approved (run {run_id}). Calendar sync will complete shortly."
         )
     ```
   - Add `import structlog` and `logger = structlog.get_logger()` at the top
   - The existing `_format_run(result)` reply can be replaced or kept as a first reply before the execution result

6. **Add `_build_task_quick_add_step()` in `workflow_runs.py`** and register in `_build_specialist_steps()`:
   - The step handler must handle the case where `_run_task_async` already called `complete_current_step` — in that case, the step is already `SUCCEEDED` and `resume_run` will move to `apply_schedule`. But for the worker recovery path (orphaned runs that never had `complete_current_step` called), the specialist step needs to do the full inference + output building.
   - `input_builder`: reads `RAW_REQUEST` artifact, extracts `request_text`
   - `handler`: calls `LLMClient().infer_task_semantics(text)`, builds `CalendarAgentOutput` (same logic as `execute_task_run` in step 2), returns it
   - `artifact_type`: `WorkflowArtifactKind.SCHEDULE_PROPOSAL`
   - `next_step_name`: `"apply_schedule"`
   - `specialist`: `SpecialistName.TASK_INFERENCE`
   - Register in `_build_specialist_steps()` under key `("task_quick_add", "infer_task_semantics")`

## Must-Haves

- [ ] `_run_task_async` calls `complete_current_step` with `SCHEDULE_PROPOSAL` artifact after inference (not just text push)
- [ ] Approval notification includes run ID, artifact ID, and `/approve` command hint
- [ ] `/approve <run_id> <artifact_id>` triggers `execute_after_approval` for immediate `apply_schedule` execution
- [ ] `_build_specialist_steps()` returns a handler for `("task_quick_add", "infer_task_semantics")`
- [ ] `past_event_guard` called before building `ScheduleBlock` in both task.py execution and worker recovery handler
- [ ] `PastEventError` caught with user-friendly message in `_run_task_async`
- [ ] All `run_in_executor` calls follow the established pattern (no `asyncio.run()` inside async handler)

## Verification

- `python -c "from helm_telegram_bot.commands import task; from helm_telegram_bot.commands import approve; print('imports ok')"`
- `python -c "from helm_worker.jobs.workflow_runs import _build_specialist_steps; steps = _build_specialist_steps(); assert ('task_quick_add', 'infer_task_semantics') in steps; print('handler registered')"`
- `python -c "from helm_orchestration.contracts import SpecialistName; print(SpecialistName.TASK_INFERENCE)"`
- Visual review: `_run_task_async` no longer references `_policy.evaluate()` or `ApprovalAction`

## Observability Impact

- Signals added/changed: structlog `task_execution_complete` (run_id, status, needs_action) in `_run_task_async`; structlog `approve_inline_execution_failed` in `approve.py`
- How a future agent inspects this: `SELECT id, status, needs_action, blocked_reason FROM workflow_runs WHERE workflow_type='task_quick_add'` — status should be `blocked` with `needs_action=True` after `/task`, then `completed` after `/approve`
- Failure state exposed: error message pushed to Telegram; `PastEventError` produces specific "time is in the past" message

## Inputs

- `apps/telegram-bot/src/helm_telegram_bot/commands/task.py` — S01's `_run_task_async` stub to replace (inference + text push)
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py` — needs new `execute_task_run` and `execute_after_approval` methods
- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — `_build_specialist_steps()` to extend with `task_quick_add` handler; `_build_resume_service` and `_build_validator_registry` and `_build_calendar_adapter` to reuse
- `packages/orchestration/src/helm_orchestration/contracts.py` — `SpecialistName` enum to extend
- S01 summary: `TaskSemantics` is the inference result; `_run_task_async` uses `run_in_executor` for LLM call; `target_artifact_id=0` sentinel must NOT be passed to orchestration service (real ID comes from approval checkpoint)
- S02 summary: `compute_reference_week(tz)`, `parse_local_slot(title, week_start, tz)`, `to_utc(dt, tz)`, `past_event_guard(dt, tz)` are the shared primitives; `settings.operator_timezone` is a string (construct `ZoneInfo()` at call time); `parse_local_slot` returns local-tz datetime, NOT UTC — must call `to_utc()` separately
- D003: Inline from Telegram handler after DB persist; worker polling retained as background recovery
- D014: past_event_guard is warn-and-skip in weekly workflow; for `/task` single-task path, raise to user since there's only one task

## Expected Output

- `apps/telegram-bot/src/helm_telegram_bot/commands/task.py` — `_run_task_async` calls `execute_task_run` → `complete_current_step` with real `CalendarAgentOutput`; pushes approval notification or success based on `needs_action`
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py` — two new methods: `execute_task_run(run_id, semantics, request_text)` and `execute_after_approval(run_id)`
- `apps/telegram-bot/src/helm_telegram_bot/commands/approve.py` — calls `execute_after_approval` after successful approval
- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — `_build_specialist_steps()` includes `("task_quick_add", "infer_task_semantics")` handler
- `packages/orchestration/src/helm_orchestration/contracts.py` — `SpecialistName.TASK_INFERENCE` added
