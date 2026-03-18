# S07: Wire `/status` command and proactive notification loop

**Goal:** `/status` is reachable from Telegram; `workflow_runs.run()` dispatches proactive approval notifications for resumed runs with `needs_action=True`; failure in one notification does not crash the worker; tests cover dispatch, no-op, and failure-isolation paths.
**Demo:** `grep "status.handle" main.py` confirms registration; `pytest tests/unit/test_worker_notification.py -v` passes 3+ tests; full suite ≥499 with no regressions.

## Must-Haves

- `workflow_runs.run()` iterates resumed `WorkflowRunState` objects after `resume_runnable_runs()` and calls `TelegramDigestDeliveryService().notify_approval_needed(run_id, proposal_summary)` for each run where `state.run.needs_action is True`
- Each notification dispatch is wrapped in individual `try/except Exception` — a failure logs `proactive_approval_notification_failed` WARNING and does NOT crash the worker or affect the return value
- `TelegramDigestDeliveryService` is imported lazily inside `run()` (not at module level) per D016
- `test_worker_notification.py` covers: notification fires for `needs_action=True`, no-op for `needs_action=False`, failure isolation (exception in one notification doesn't crash the loop)
- `test_worker_registry.py` fake states updated from bare `object()` to objects with `.run.needs_action=False` so the notification loop doesn't crash on them
- `/status` remains registered as `CommandHandler("status", status.handle)` in `main.py` (already done — verified in planning)
- Full test suite ≥499 with no regressions

## Verification

- `grep -n 'CommandHandler("status"' apps/telegram-bot/src/helm_telegram_bot/main.py` → matches `status.handle`
- `grep -n "notify_approval_needed\|needs_action" apps/worker/src/helm_worker/jobs/workflow_runs.py` → shows notification call and needs_action check
- `OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen pytest tests/unit/test_worker_notification.py -v` → 3+ passed
- `OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen pytest tests/unit/test_worker_registry.py -v` → 3 passed (no regression)
- `OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen pytest tests/unit/ tests/integration/ --ignore=tests/integration/test_study_agent_mvp.py --ignore=tests/unit/test_study_agent_mvp.py --tb=short` → ≥499 passed

## Observability / Diagnostics

- Runtime signals: structlog INFO `proactive_approval_notification_sent` (run_id, workflow_type) on success; structlog WARNING `proactive_approval_notification_failed` (run_id, exc_info=True) on failure
- Inspection surfaces: `grep "proactive_approval_notification" <worker-log-stream>`
- Failure visibility: per-run exception logged with full traceback; worker continues normally; return value unaffected
- Redaction constraints: none

## Integration Closure

- Upstream surfaces consumed: `TelegramDigestDeliveryService.notify_approval_needed()` from `digest_delivery.py`; `WorkflowRunState.run.needs_action` from `helm_storage`; `WorkflowArtifactType.SCHEDULE_PROPOSAL` for proposal_summary extraction
- New wiring introduced in this slice: notification dispatch loop in `workflow_runs.run()`
- What remains before the milestone is truly usable end-to-end: nothing — this is the final M004 slice

## Tasks

- [x] **T01: Add proactive notification loop to workflow_runs.run() and write tests** `est:30m`
  - Why: The notification loop is the only missing production wiring in M004 — without it, the worker silently resumes runs that need approval without notifying the operator. The `/status` command registration is already done (verified: `CommandHandler("status", status.handle)` exists at line 100 of `main.py`). This task adds the loop, fixes the existing test fake states, and writes new tests.
  - Files: `apps/worker/src/helm_worker/jobs/workflow_runs.py`, `tests/unit/test_worker_notification.py`, `tests/unit/test_worker_registry.py`
  - Do: (1) Add notification loop to `run()` after `resume_runnable_runs()` — iterate `resumed`, skip if `not state.run.needs_action`, extract `proposal_summary` from `state.latest_artifacts`, lazily import and call `TelegramDigestDeliveryService().notify_approval_needed()`, wrap each dispatch in `try/except Exception`. (2) Fix `_FakeResumeService` in `test_worker_registry.py` to return fake states with `.run.needs_action=False` instead of bare `object()`. (3) Write `test_worker_notification.py` with 3+ tests covering dispatch, no-op, and failure isolation.
  - Verify: `OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen pytest tests/unit/test_worker_notification.py tests/unit/test_worker_registry.py -v` → all pass; full suite ≥499
  - Done when: notification loop present in `workflow_runs.run()`, 3+ new tests pass, existing registry tests pass, full suite ≥499

## Files Likely Touched

- `apps/worker/src/helm_worker/jobs/workflow_runs.py`
- `tests/unit/test_worker_notification.py`
- `tests/unit/test_worker_registry.py`
