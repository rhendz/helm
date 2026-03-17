---
estimated_steps: 5
estimated_files: 1
---

# T04: Add /task → DB state integration test

**Slice:** S05 — Strict test boundaries and real E2E calendar coverage
**Milestone:** M004

## Description

S03's known limitation: "No integration test for the full `/task` → DB → notification chain." This task creates `tests/integration/test_task_execution_integration.py` that exercises the `/task` → `execute_task_run` → DB state path with real Postgres (in-memory SQLite), mocked LLM, and mocked Calendar adapter — a proper integration test per R113/D007.

The test proves the inline execution path produces the correct DB state transitions:
- After `execute_task_run`: `status=blocked`, `needs_action=True`
- After `execute_after_approval`: `status=completed`, `needs_action=False`

**Independent of T01-T03** — only requires S03's files which are already complete.

**Key constraint**: Must use time-freeze pattern (D015) to avoid `past_event_guard` flakiness mid-week. Use a task title with a far-future date like "dentist appointment 2099-01-07 at 9am" or freeze time to a future Monday (2099-01-05 00:01 UTC).

## Steps

1. **Create `tests/integration/test_task_execution_integration.py`** with the following structure:
   - Import the same session setup pattern as `test_weekly_scheduling_end_to_end.py`: in-memory SQLite engine, `StaticPool`, `create_tables`, `sessionmaker`.
   - Import `TelegramWorkflowStatusService` (the telegram-bot service that wraps `start_task_run`, `execute_task_run`, `execute_after_approval`).
   - Import `TaskSemantics` from `helm_llm.inference`.
   - Import session/DB fixtures from existing patterns.

2. **Write `_SessionContext` helper** (same pattern as existing integration tests):
   ```python
   class _SessionContext:
       def __init__(self, session):
           self._session = session
       def __enter__(self):
           return self._session
       def __exit__(self, *args):
           return False
   ```

3. **Write `test_task_execution_creates_blocked_run_and_completes_after_approval`**:
   - Set up in-memory SQLite DB with `Base.metadata.create_all(engine)`.
   - Create a `TaskSemantics` with known values: `urgency="low"`, `priority="p3"`, `sizing_minutes=60`, `confidence="high"`.
   - Use `monkeypatch` to:
     - Patch `helm_storage.db.SessionLocal` → return `_SessionContext(session)` (so service calls use test session).
     - Patch `helm_worker.jobs.workflow_runs.SessionLocal` the same way.
     - Patch `helm_orchestration.scheduling.datetime` for time-freeze to 2099-01-05 00:01 UTC (future Monday).
     - Patch `google.oauth2.credentials.Credentials` and `googleapiclient.discovery.build` to prevent real API calls from `_build_calendar_adapter`.
   - Call `TelegramWorkflowStatusService().start_task_run(request_text="dentist Monday 9am", submitted_by="test", chat_id="test")`.
   - Call `TelegramWorkflowStatusService().execute_task_run(run_id, semantics=semantics, request_text="dentist Monday 9am")`.
   - Assert result: `status == "blocked"`, `needs_action == True`.
   - Approve the run: call `WorkflowStatusService(session).approve_run(run_id, actor="test", target_artifact_id=...)`.
   - Call `TelegramWorkflowStatusService().execute_after_approval(run_id)`.
   - Assert result: `status == "completed"`, `needs_action == False`.

4. **Handle the `past_event_guard` correctly**: The task title "dentist Monday 9am" with time frozen to 2099-01-05 (Monday) means `parse_local_slot` will return 2099-01-05 09:00 in OPERATOR_TIMEZONE, which is in the future. The `past_event_guard` will pass. This avoids needing a far-future explicit date in the title.

5. **Run and verify**:
   ```bash
   OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/integration/test_task_execution_integration.py -v
   ```

**Important implementation notes for the executor**:
- `TelegramWorkflowStatusService` uses `SessionLocal` from `helm_storage.db` — monkeypatch that module's `SessionLocal`.
- `execute_task_run` does lazy imports of `_build_calendar_adapter` and `_build_validator_registry` from `helm_worker.jobs.workflow_runs` — that module also uses `SessionLocal` for DB access.
- `_build_calendar_adapter` constructs `GoogleCalendarAdapter(GoogleCalendarAuth())` — mock `GoogleCalendarAuth` or `google.oauth2.credentials.Credentials` to prevent real credential loading.
- The mock calendar adapter must return successful `CalendarSyncResult` objects for `upsert_calendar_block` calls during `execute_after_approval`.
- Follow the existing integration test pattern in `tests/integration/test_weekly_scheduling_end_to_end.py` for session management — `_SessionContext` wrapper + `monkeypatch.setattr`.

## Must-Haves

- [ ] `tests/integration/test_task_execution_integration.py` exists
- [ ] Test uses in-memory SQLite (or test Postgres), not external services
- [ ] LLM is mocked (no real OpenAI calls)
- [ ] Calendar adapter is mocked (no real Google Calendar calls)
- [ ] Test asserts `status=blocked, needs_action=True` after `execute_task_run`
- [ ] Test asserts `status=completed, needs_action=False` after `execute_after_approval`
- [ ] Time-freeze pattern used to avoid `past_event_guard` flakiness (D015)
- [ ] Test passes in CI without any external services beyond the test DB

## Verification

- ```bash
  OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/integration/test_task_execution_integration.py -v
  ```
  → Test passes

- ```bash
  OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/integration/ -q
  ```
  → All integration tests pass (no regressions)

## Inputs

- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py` — `TelegramWorkflowStatusService` with `start_task_run`, `execute_task_run`, `execute_after_approval`
- `packages/llm/src/helm_llm/inference.py` — `TaskSemantics` Pydantic model
- `tests/integration/test_weekly_scheduling_end_to_end.py` — reference pattern for `_SessionContext`, session setup, monkeypatching
- S02 forward intelligence: time-freeze pattern — patch `helm_orchestration.scheduling.datetime`, set now to 2099-01-05 00:01 UTC, delegate constructor via `mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)`
- S03 forward intelligence: `execute_task_run` builds `CalendarAgentOutput` from `TaskSemantics` using `parse_local_slot`, `to_utc`, `past_event_guard`

## Expected Output

- `tests/integration/test_task_execution_integration.py` — new file with at least one test proving the full `/task` → DB state path with correct state transitions (blocked → completed)

## Observability Impact

**What signals change:**
- `WorkflowRun.status` transitions (`pending → blocked → pending → completed`) and `needs_action` flip are the primary observable signals — both are surfaced via `GET /v1/workflow-runs/{run_id}` or `WorkflowStatusService.get_run_detail(run_id)`.
- `StubCalendarSystemAdapter.upsert_calendar_block` is invoked during `execute_after_approval`; real adapter logs `upsert_calendar_block` structlog entry with `planned_item_key` — filter structlog for `key="upsert_calendar_block"` to confirm calendar write was reached.
- `PastEventError` raised from `past_event_guard` appears in logs when time-freeze is not applied correctly — signals misconfiguration of the time mock.

**How to inspect after the fact:**
- `session.get(WorkflowRunORM, run_id)` gives raw ORM state at any checkpoint.
- `WorkflowStatusService(session).get_run_detail(run_id)` returns the full run detail dict including `approval_checkpoint`, `current_step`, `status`, and `needs_action`.
- Query `SELECT status, needs_action FROM workflow_runs WHERE id = <run_id>` in the test DB for post-hoc inspection.

**Failure visibility:**
- If `past_event_guard` fires, the test fails at `execute_task_run` with `PastEventError` — indicates the `helm_orchestration.scheduling.datetime` patch was not applied correctly or the frozen time is in the past.
- If `_build_calendar_adapter` cannot connect, it logs `calendar_adapter_fallback_to_stub` at WARNING and falls back to `StubCalendarSystemAdapter` — this is expected in the test environment and is harmless.
- If `get_run_detail` returns `None`, the run was created in a different session than the one being inspected — indicates session isolation is broken in the test setup.
