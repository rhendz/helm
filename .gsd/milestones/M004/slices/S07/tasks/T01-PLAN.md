---
estimated_steps: 5
estimated_files: 3
---

# T01: Add proactive notification loop to workflow_runs.run() and write tests

**Slice:** S07 — Wire `/status` command and proactive notification loop
**Milestone:** M004

## Description

The worker's `workflow_runs.run()` function resumes runnable workflow runs but does not notify the operator when a run reaches `needs_action=True`. This task adds a post-resume notification loop that calls `TelegramDigestDeliveryService().notify_approval_needed()` for each run needing approval, with per-run failure isolation. It also fixes `test_worker_registry.py` fake states (which use bare `object()` that will crash with the new loop) and writes `test_worker_notification.py` with 3+ tests.

**Note:** `/status` registration in `main.py` is already complete — `CommandHandler("status", status.handle)` exists at line 100. No changes needed there.

## Steps

1. **Add notification loop to `workflow_runs.run()`** in `apps/worker/src/helm_worker/jobs/workflow_runs.py`:
   - After `logger.info("workflow_runs_job_processed", resumed_count=len(resumed))` and before `return len(resumed)`, add a loop:
   ```python
   # Fire proactive notifications for any run that reached needs_action=True
   for state in resumed:
       if not state.run.needs_action:
           continue
       try:
           from helm_telegram_bot.services.digest_delivery import TelegramDigestDeliveryService
           proposal_summary = ""
           schedule_proposal = state.latest_artifacts.get(
               WorkflowArtifactType.SCHEDULE_PROPOSAL.value
           )
           if schedule_proposal is not None:
               proposal_summary = schedule_proposal.payload.get("proposal_summary") or ""
           TelegramDigestDeliveryService().notify_approval_needed(
               state.run.id, proposal_summary
           )
           logger.info(
               "proactive_approval_notification_sent",
               run_id=state.run.id,
               workflow_type=state.run.workflow_type,
           )
       except Exception:
           logger.warning(
               "proactive_approval_notification_failed",
               run_id=state.run.id,
               exc_info=True,
           )
   ```
   - **CRITICAL CONSTRAINT (D016):** `TelegramDigestDeliveryService` must be imported **lazily inside the loop body** (not at module level). The module-level import that exists in the current file (`from helm_telegram_bot.services.digest_delivery import TelegramDigestDeliveryService`) was added by the S06 merge but S07 research says it should be lazy. Check if there's already a module-level import — if so, **remove it** and move the import inside the loop's try block. If removing the module-level import breaks anything else in the file, keep it but ensure the notification path uses the lazy import inside try/except so that import failures are caught gracefully.
   - **IMPORTANT:** The `return len(resumed)` return value must NOT be affected by notification failures. The notification loop runs after the count is computed and before the return.

2. **Fix fake states in `test_worker_registry.py`** at `tests/unit/test_worker_registry.py`:
   - The `_FakeResumeService` in `test_workflow_runs_job_resumes_runnable_runs` returns `[object(), object()]`. The notification loop accesses `state.run.needs_action`, which will raise `AttributeError` on bare `object()`.
   - Replace with properly shaped fake states. Add a simple dataclass or use `types.SimpleNamespace`:
   ```python
   import types
   
   def _make_fake_state(needs_action=False):
       run = types.SimpleNamespace(needs_action=needs_action)
       return types.SimpleNamespace(run=run, latest_artifacts={})
   ```
   - Update `_FakeResumeService.resume_runnable_runs()` to return `[_make_fake_state(), _make_fake_state()]`.

3. **Write `tests/unit/test_worker_notification.py`** with these test cases:
   - **`test_notification_fires_for_needs_action_true`**: Create a fake state with `run.needs_action=True`, `run.id=42`, `run.workflow_type="task_quick_add"`, and `latest_artifacts={}`. Monkeypatch `workflow_runs._build_specialist_steps` to return a handler, `workflow_runs.SessionLocal` to yield a session, and `workflow_runs._build_resume_service` to return a service that yields this state. Also monkeypatch `helm_telegram_bot.services.digest_delivery.TelegramDigestDeliveryService.notify_approval_needed` to capture calls. Assert `notify_approval_needed` was called with `(42, "")`.
   - **`test_no_notification_for_needs_action_false`**: Same setup but `run.needs_action=False`. Assert `notify_approval_needed` was NOT called.
   - **`test_notification_failure_does_not_crash_loop`**: Two fake states both with `needs_action=True` (run IDs 1 and 2). Mock `notify_approval_needed` to raise `RuntimeError` on first call and succeed on second. Assert `run()` returns 2 (both resumed), and `notify_approval_needed` was called twice (failure didn't stop the loop).
   - **`test_proposal_summary_extracted_from_artifact`**: Fake state with `needs_action=True` and `latest_artifacts` containing a `WorkflowArtifactType.SCHEDULE_PROPOSAL.value` key mapped to a SimpleNamespace with `payload={"proposal_summary": "Schedule: test task"}`. Assert `notify_approval_needed` was called with the extracted summary.
   - Use `monkeypatch` throughout. Import `workflow_runs` and patch at module level. Use `contextlib.contextmanager` for the `SessionLocal` mock. Use `types.SimpleNamespace` for fake objects.
   - Each test must set `OPERATOR_TIMEZONE` env var or the conftest must handle it.

4. **Verify `/status` registration exists** — run:
   ```bash
   grep -n 'CommandHandler("status"' apps/telegram-bot/src/helm_telegram_bot/main.py
   ```
   Expected: matches `CommandHandler("status", status.handle)`. No changes needed.

5. **Run full verification**:
   ```bash
   OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen pytest tests/unit/test_worker_notification.py -v
   OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen pytest tests/unit/test_worker_registry.py -v
   OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen pytest tests/unit/ tests/integration/ \
     --ignore=tests/integration/test_study_agent_mvp.py \
     --ignore=tests/unit/test_study_agent_mvp.py --tb=short
   ```

## Must-Haves

- [ ] `workflow_runs.run()` iterates resumed states and calls `notify_approval_needed()` for each `needs_action=True` run
- [ ] Each notification wrapped in individual `try/except Exception` — failure logs WARNING, does not crash
- [ ] `TelegramDigestDeliveryService` imported lazily (inside loop body), not at module level (D016)
- [ ] `test_worker_registry.py` fake states have `.run.needs_action=False` attribute
- [ ] `test_worker_notification.py` has ≥3 tests covering dispatch, no-op, and failure isolation
- [ ] `return len(resumed)` is unaffected by notification errors
- [ ] Full test suite ≥499 with no regressions

## Verification

- `grep -n "notify_approval_needed\|needs_action" apps/worker/src/helm_worker/jobs/workflow_runs.py` → shows notification loop
- `OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen pytest tests/unit/test_worker_notification.py -v` → ≥3 passed
- `OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen pytest tests/unit/test_worker_registry.py -v` → 3 passed
- `OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen pytest tests/unit/ tests/integration/ --ignore=tests/integration/test_study_agent_mvp.py --ignore=tests/unit/test_study_agent_mvp.py --tb=short` → ≥499 passed
- `grep -n 'CommandHandler("status"' apps/telegram-bot/src/helm_telegram_bot/main.py` → confirms `/status` already registered

## Observability Impact

- Signals added: structlog INFO `proactive_approval_notification_sent` (run_id, workflow_type); structlog WARNING `proactive_approval_notification_failed` (run_id, exc_info=True)
- How a future agent inspects this: `grep "proactive_approval_notification" <worker-logs>`
- Failure state exposed: per-run exception with full traceback logged at WARNING; worker continues

## Inputs

- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — current `run()` function resumes runs but has no notification dispatch; `TelegramDigestDeliveryService` may be imported at module level from S06 merge (needs to be moved to lazy if so)
- `apps/telegram-bot/src/helm_telegram_bot/services/digest_delivery.py` — `notify_approval_needed(run_id, proposal_summary)` method already exists and works; no changes needed
- `tests/unit/test_worker_registry.py` — `_FakeResumeService` returns `[object(), object()]` which will crash with the new notification loop
- `packages/storage/src/helm_storage/repositories/contracts.py` — `WorkflowRunState` is a frozen dataclass with `.run` (WorkflowRunORM, has `.needs_action`, `.id`, `.workflow_type`) and `.latest_artifacts` (dict[str, WorkflowArtifactORM])
- `WorkflowArtifactType.SCHEDULE_PROPOSAL.value` is the key for proposal artifacts in `latest_artifacts`

## Expected Output

- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — `run()` has notification loop after `resume_runnable_runs()`; `TelegramDigestDeliveryService` imported lazily inside loop
- `tests/unit/test_worker_notification.py` — new file with ≥3 passing tests
- `tests/unit/test_worker_registry.py` — fake states updated to have `.run.needs_action=False`
