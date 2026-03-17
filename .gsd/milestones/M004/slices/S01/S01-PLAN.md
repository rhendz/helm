# S01: Task inference engine and `/task` quick-add

**Goal:** `/task <natural language>` persists a task workflow run immediately, infers semantics (urgency/priority/sizing/confidence) via LLM, evaluates a conditional approval policy, and pushes the outcome to the operator — all completing within seconds of the command.

**Demo:** Operator sends `/task need to book flights this week` → immediate ack ("Task received — analyzing…") → follow-up message within 5s showing inferred semantics and either "✅ Auto-approved" or "⚠️ Approval needed" based on confidence/sizing thresholds.

## Must-Haves

- `TaskSemantics` Pydantic model with urgency, priority, sizing_minutes, confidence fields — usable as `text_format` target for `responses.parse`
- `WeeklyTaskRequest` extended with `urgency: str | None = None` and `confidence: float | None = None` (backward-compatible)
- `ConditionalApprovalPolicy.evaluate(semantics) -> ApprovalDecision` — auto-approves when confidence ≥ 0.8 AND sizing ≤ 120min, requests revision otherwise
- `LLMClient.infer_task_semantics(text) -> TaskSemantics` using `responses.parse` structured output
- `/task` Telegram command: auth guard → ack reply → background task (inference + policy + push outcome)
- Workflow run persisted to DB with `workflow_type="task_quick_add"` before background work begins
- Background inference runs in executor (not blocking PTB event loop); errors caught and pushed as user-facing messages
- Unit tests for inference (mocked LLM), approval policy (table-driven), and command handler (monkeypatched service)

## Proof Level

- This slice proves: contract + integration (types, inference, policy logic, handler wiring)
- Real runtime required: no (unit tests with mocked LLM and monkeypatched services)
- Human/UAT required: yes (manual `/task` smoke test deferred to S03 integration, but handler is testable in isolation)

## Verification

- `uv run --frozen --extra dev pytest tests/unit/test_task_inference.py -v` — all pass (inference mock, approval policy table-driven)
- `uv run --frozen --extra dev pytest tests/unit/test_task_command.py -v` — all pass (ack sent, background task launched, error handling)
- `bash scripts/test.sh` — full suite passes (no regressions from schema extension or new exports)

## Observability / Diagnostics

- Runtime signals: structlog entries for task inference start/complete/error with task text and inferred semantics
- Inspection surfaces: `workflow_runs` DB table shows `workflow_type="task_quick_add"` entries
- Failure visibility: background task catches all exceptions and pushes error message to operator chat; structlog error entry with traceback
- Redaction constraints: raw task text is logged; no secrets or PII in inference payload

## Integration Closure

- Upstream surfaces consumed: `LLMClient` (`packages/llm/client.py`), `WorkflowOrchestrationService.create_run()` (`packages/orchestration/workflow_service.py`), `TelegramWorkflowStatusService` (`apps/telegram-bot/services/workflow_status_service.py`), auth guard (`commands/common.py`), PTB `CommandHandler` registration (`main.py`)
- New wiring introduced in this slice: `/task` command handler registered in `main.py`; `start_task_run()` method on `TelegramWorkflowStatusService`; `TaskSemantics` and `ConditionalApprovalPolicy` exported from `helm_orchestration`
- What remains before the milestone is truly usable end-to-end: S02 (timezone correctness, shared scheduling primitives, calendar placement), S03 (immediate execution path for full workflow), S04 (Telegram UX polish)

## Tasks

- [ ] **T01: Define TaskSemantics model, approval policy stub, and LLM inference method** `est:1h`
  - Why: Establishes the shared domain types and inference capability that the `/task` handler consumes. These are pure library additions with no runtime wiring — tested in isolation.
  - Files: `packages/orchestration/src/helm_orchestration/schemas.py`, `packages/orchestration/src/helm_orchestration/scheduling.py` (new), `packages/orchestration/src/helm_orchestration/__init__.py`, `packages/llm/src/helm_llm/client.py`, `tests/unit/test_task_inference.py` (new)
  - Do: (1) Add `TaskSemantics` Pydantic model to `schemas.py` with `urgency: str`, `priority: str`, `sizing_minutes: int`, `confidence: float` — use `extra="ignore"` not `extra="forbid"` since it's an LLM parse target. (2) Add `urgency: str | None = None` and `confidence: float | None = None` to `WeeklyTaskRequest`. (3) Create `scheduling.py` with `ApprovalPolicy` Protocol and `ConditionalApprovalPolicy` class — `evaluate(semantics) -> ApprovalDecision` returns APPROVE when confidence ≥ 0.8 and sizing_minutes ≤ 120, else REQUEST_REVISION. (4) Export new types from `__init__.py`. (5) Add `infer_task_semantics(text) -> TaskSemantics` to `LLMClient` using `self._client.responses.parse(model=..., instructions=..., input=text, text_format=TaskSemantics)`. (6) Write `test_task_inference.py` with mocked LLM response and table-driven approval policy tests.
  - Verify: `uv run --frozen --extra dev pytest tests/unit/test_task_inference.py -v` — all pass
  - Done when: `TaskSemantics` importable from `helm_orchestration`, `ConditionalApprovalPolicy.evaluate()` returns correct decisions for edge cases, `LLMClient.infer_task_semantics()` exists and is tested with mocked OpenAI

- [ ] **T02: Wire `/task` command handler with ack + background inference pattern** `est:1h`
  - Why: Makes the feature operator-visible. This is the main deliverable — the Telegram handler that ties together inference, approval policy, run persistence, and async execution.
  - Files: `apps/telegram-bot/src/helm_telegram_bot/commands/task.py` (new), `apps/telegram-bot/src/helm_telegram_bot/main.py`, `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`, `tests/unit/test_task_command.py` (new)
  - Do: (1) Add `start_task_run(request_text, submitted_by, chat_id) -> dict` to `TelegramWorkflowStatusService` mirroring `start_run()` but with `workflow_type="task_quick_add"` and `first_step_name="infer_task_semantics"`. (2) Create `task.py` handler: auth guard → validate args → ack reply ("Task received — analyzing…") → `context.application.create_task(_run_task_async(...))`. (3) Implement `_run_task_async()`: wrap `LLMClient.infer_task_semantics()` in `run_in_executor(None, ...)` to avoid blocking PTB event loop; evaluate `ConditionalApprovalPolicy`; format and push follow-up message; catch all exceptions and push error message. (4) Register handler in `main.py`: `application.add_handler(CommandHandler("task", task.handle))`. (5) Write `test_task_command.py` following existing pattern in `test_workflow_telegram_commands.py` — test ack sent, correct follow-up format, error handling on inference failure.
  - Verify: `uv run --frozen --extra dev pytest tests/unit/test_task_command.py -v` and `bash scripts/test.sh` — all pass
  - Done when: `/task` handler registered, ack reply sent immediately on command, background task runs inference and pushes outcome, error case pushes user-friendly message, full test suite green

## Files Likely Touched

- `packages/orchestration/src/helm_orchestration/schemas.py`
- `packages/orchestration/src/helm_orchestration/scheduling.py` (new)
- `packages/orchestration/src/helm_orchestration/__init__.py`
- `packages/llm/src/helm_llm/client.py`
- `apps/telegram-bot/src/helm_telegram_bot/commands/task.py` (new)
- `apps/telegram-bot/src/helm_telegram_bot/main.py`
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`
- `tests/unit/test_task_inference.py` (new)
- `tests/unit/test_task_command.py` (new)
