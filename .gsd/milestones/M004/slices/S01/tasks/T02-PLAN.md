---
estimated_steps: 5
estimated_files: 4
---

# T02: Wire `/task` command handler with ack + background inference pattern

**Slice:** S01 — Task inference engine and `/task` quick-add
**Milestone:** M004

## Description

Create the `/task` Telegram command handler that makes the inference engine and approval policy operator-visible. The handler persists a workflow run immediately, sends an ack ("Task received — analyzing…"), then runs inference + approval evaluation as a background async task and pushes the outcome. This is the integration task that wires T01's building blocks into the Telegram bot runtime.

**Key constraints from research:**
- Use `context.application.create_task(coroutine)` for background execution (PTB 22.6 API)
- Wrap `LLMClient.infer_task_semantics()` in `await loop.run_in_executor(None, ...)` — OpenAI SDK is synchronous and will block the PTB event loop if called directly
- Do NOT use `asyncio.run()` or `TelegramDigestDeliveryService.deliver()` — they conflict with the running event loop
- Use `await update.message.reply_text(...)` directly for the follow-up push (the update object is captured in the closure)
- Catch ALL exceptions in the background coroutine and push an error message — PTB 22 silently drops uncaught exceptions in `create_task()` coroutines
- `workflow_type="task_quick_add"` — `WorkflowOrchestrationService.create_run()` accepts any string; `workflow_service.py` only has special logic for `weekly_scheduling`
- Existing `/tasks` command (plural, `tasks.py`) lists email tasks — new file is `task.py` (singular), no conflict
- Follow handler pattern from `commands/workflows.py` — `reject_if_unauthorized()` guard, module-level `_service` instance

**Existing test pattern** (from `test_workflow_telegram_commands.py`):
- `_Update` class with `_Message` that captures `.replies` list
- `_Context` class with `.args` list
- Monkeypatch `reject_if_unauthorized` to return `False` (allow) 
- Monkeypatch `_service` with a stub class

## Steps

1. **Add `start_task_run()` to `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`:**
   Mirror the existing `start_run()` method but with `workflow_type="task_quick_add"` and `first_step_name="infer_task_semantics"`. The method signature: `start_task_run(self, *, request_text: str, submitted_by: str, chat_id: str) -> dict[str, object]`. Internally, it calls `self._orchestration_service.create_run(...)` with `workflow_type="task_quick_add"`, `first_step_name="infer_task_semantics"`, and builds the request input using the same pattern as `start_run()`. Return the same status dict shape that `start_run()` returns.

2. **Create `apps/telegram-bot/src/helm_telegram_bot/commands/task.py`:**
   ```python
   import asyncio
   import structlog
   from telegram import Update
   from telegram.ext import ContextTypes
   from helm_telegram_bot.commands.common import reject_if_unauthorized
   from helm_telegram_bot.services.workflow_status_service import TelegramWorkflowStatusService
   from helm_orchestration import TaskSemantics, ConditionalApprovalPolicy, ApprovalAction
   from helm_llm.client import LLMClient

   logger = structlog.get_logger()
   _service = TelegramWorkflowStatusService()
   _policy = ConditionalApprovalPolicy()

   async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
       if await reject_if_unauthorized(update, context):
           return
       if not update.message or not context.args:
           await update.message.reply_text("Usage: /task <description>")
           return
       task_text = " ".join(context.args)
       user_id = str(update.effective_user.id)
       chat_id = str(update.message.chat_id)

       # Persist run immediately (crash-safe)
       run_info = _service.start_task_run(
           request_text=task_text, submitted_by=f"telegram:{user_id}", chat_id=chat_id
       )
       run_id = run_info["id"]

       # Ack immediately
       await update.message.reply_text(f"Task received — analyzing… (run {run_id})")

       # Background: inference + policy + push outcome
       context.application.create_task(
           _run_task_async(update, task_text, run_id),
           update=update,
       )

   async def _run_task_async(update: Update, task_text: str, run_id: int) -> None:
       try:
           loop = asyncio.get_event_loop()
           client = LLMClient()
           semantics = await loop.run_in_executor(
               None, client.infer_task_semantics, task_text
           )
           decision = _policy.evaluate(semantics)
           # Format outcome message
           lines = [
               f"📋 *Task Analysis* (run {run_id})",
               f"Urgency: {semantics.urgency} | Priority: {semantics.priority}",
               f"Estimated: {semantics.sizing_minutes}min | Confidence: {semantics.confidence:.0%}",
           ]
           if decision.action == ApprovalAction.APPROVE:
               lines.append("✅ Auto-approved — ready for scheduling")
           else:
               lines.append("⚠️ Needs review — approval required")
               if decision.revision_feedback:
                   lines.append(f"Reason: {decision.revision_feedback}")
           await update.message.reply_text("\n".join(lines))
           logger.info("task_inference_complete", run_id=run_id, urgency=semantics.urgency,
                       priority=semantics.priority, sizing=semantics.sizing_minutes,
                       confidence=semantics.confidence, decision=decision.action)
       except Exception:
           logger.exception("task_inference_failed", run_id=run_id)
           await update.message.reply_text(
               f"❌ Task analysis failed for run {run_id}. The task is saved — retry with /task or check /status."
           )
   ```
   Important: the `try/except` around the entire background coroutine ensures the operator always gets feedback, even on failure. PTB silently drops uncaught exceptions in `create_task()`.

3. **Register handler in `apps/telegram-bot/src/helm_telegram_bot/main.py`:**
   Add `from helm_telegram_bot.commands import task` to imports. Add `application.add_handler(CommandHandler("task", task.handle))` alongside the existing handler registrations. Place it near the other command handlers.

4. **Write `tests/unit/test_task_command.py`:**
   Follow the exact pattern from `tests/unit/test_workflow_telegram_commands.py`:
   - Reuse `_Update`, `_Message`, `_Context` helper classes (or import if factored out — check first; if not factored out, define locally)
   - `_Context` for this handler needs an additional `.application` attribute with a `create_task()` method that captures the coroutine
   - Test cases:
     - **No args → usage message:** `/task` with empty args returns "Usage: /task <description>"
     - **Ack sent immediately:** `/task book flights` sends "Task received — analyzing…" as first reply
     - **Background task created:** Verify `create_task()` was called with a coroutine
     - **Successful inference → formatted outcome:** Mock `LLMClient.infer_task_semantics` to return a `TaskSemantics` instance; run the background coroutine; verify the follow-up message contains urgency/priority/sizing and approval status
     - **Inference failure → error message:** Mock `LLMClient.infer_task_semantics` to raise `RuntimeError`; run the background coroutine; verify error message pushed
   - Monkeypatch targets: `task.reject_if_unauthorized` (return False), `task._service` (stub with `start_task_run` returning `{"id": 1, ...}`), `task.LLMClient` or `task._run_task_async` internals

5. **Run full test suite to confirm no regressions:**
   `bash scripts/test.sh` must pass. Key regression risk: `WeeklyTaskRequest` field additions (already mitigated by `None` defaults in T01) and new imports in `__init__.py`.

## Must-Haves

- [ ] `start_task_run()` on `TelegramWorkflowStatusService` creates a run with `workflow_type="task_quick_add"`
- [ ] `/task` handler sends ack reply within the synchronous handler path (before background task)
- [ ] Background inference runs in `run_in_executor` — does NOT block PTB event loop
- [ ] All exceptions in background coroutine caught and pushed as user-facing error messages
- [ ] Handler registered in `main.py` via `CommandHandler("task", task.handle)`
- [ ] Unit tests cover: no-args usage, ack message, successful inference outcome, inference failure error
- [ ] Full test suite passes (`bash scripts/test.sh`)

## Verification

- `cd /Users/ankush/git/helm/.gsd/worktrees/M004 && uv run --frozen --extra dev pytest tests/unit/test_task_command.py -v` — all tests pass
- `cd /Users/ankush/git/helm/.gsd/worktrees/M004 && bash scripts/test.sh` — full suite passes
- `grep -n "task.handle" apps/telegram-bot/src/helm_telegram_bot/main.py` — handler is registered

## Observability Impact

- Signals added: `task_inference_complete` structlog event (run_id, urgency, priority, sizing, confidence, decision); `task_inference_failed` structlog exception event (run_id)
- How a future agent inspects this: `grep "task_inference" <logs>` to find inference results; query `workflow_runs` table for `workflow_type='task_quick_add'`
- Failure state exposed: operator receives explicit "❌ Task analysis failed" message with run ID; structlog captures full traceback

## Inputs

- `packages/orchestration/src/helm_orchestration/schemas.py` — `TaskSemantics` model (from T01)
- `packages/orchestration/src/helm_orchestration/scheduling.py` — `ConditionalApprovalPolicy` (from T01)
- `packages/llm/src/helm_llm/client.py` — `LLMClient.infer_task_semantics()` (from T01)
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py` — reference handler pattern (auth guard, service usage)
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py` — existing `start_run()` method to mirror
- `tests/unit/test_workflow_telegram_commands.py` — reference test pattern (`_Update`, `_Message`, `_Context` stubs, monkeypatch approach)
- `apps/telegram-bot/src/helm_telegram_bot/commands/common.py` — `reject_if_unauthorized()` import

## Expected Output

- `apps/telegram-bot/src/helm_telegram_bot/commands/task.py` — new handler file
- `apps/telegram-bot/src/helm_telegram_bot/main.py` — `/task` handler registered
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py` — `start_task_run()` method added
- `tests/unit/test_task_command.py` — new test file with passing unit tests
