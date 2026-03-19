# S06: Delete packages/connectors + Protocol Finalization

**Goal:** `packages/connectors/` is fully deleted, all import sites reference `helm_orchestration` for stubs, `CalendarProvider` + `InboxProvider` Protocol classes are confirmed in `packages/providers/`, and `scripts/test.sh` is green.
**Demo:** `rg "helm_connectors" apps/ packages/ tests/ -t py` returns zero results; `ls packages/connectors/` fails; `bash scripts/test.sh` passes with 0 failures.

## Must-Haves

- Two e2e test files deleted (`test_weekly_scheduling_calendar_e2e.py`, `test_weekly_scheduling_full_stack_e2e.py`) to unblock test collection
- `StubCalendarSystemAdapter` and `StubTaskSystemAdapter` moved to `packages/orchestration/src/helm_orchestration/stubs.py` and re-exported from `helm_orchestration/__init__.py`
- All 12 import sites (`apps/` + `tests/`) updated from `helm_connectors` to `helm_orchestration`
- `packages/connectors/` directory deleted entirely (including `__pycache__/`)
- `pyproject.toml` `[tool.setuptools.packages.find].where` entry for `packages/connectors/src` removed
- 5 pre-existing test failures in `test_worker_notification.py` (4) and `test_worker_registry.py` (1) fixed by mocking `_resolve_bootstrap_user_id`
- `scripts/test.sh` passes with 0 failures

## Proof Level

- This slice proves: final-assembly
- Real runtime required: no (import hygiene + unit/integration tests)
- Human/UAT required: no (UAT is a separate milestone-level gate)

## Verification

- `rg "helm_connectors" apps/ packages/ tests/ -t py` → zero results (comments in `helm_providers/gmail.py` are acceptable; they reference the old package name in docstrings, not imports)
- `test ! -d packages/connectors` → exit 0
- `uv run python -c "from helm_orchestration import StubCalendarSystemAdapter, StubTaskSystemAdapter; print('ok')"` → prints `ok`
- `uv run python -c "from helm_connectors import StubCalendarSystemAdapter"` → `ModuleNotFoundError`
- `uv run python -c "from helm_providers import CalendarProvider, InboxProvider; print('ok')"` → prints `ok`
- `bash scripts/test.sh` → 0 failures

## Observability / Diagnostics

- **Runtime signals:** No new runtime signals introduced — this slice is import hygiene only. Both stub classes (`StubCalendarSystemAdapter`, `StubTaskSystemAdapter`) emit no logs themselves; callers in `workflow_runs.py` and `workflow_status_service.py` produce existing structured log output via `helm_observability`.
- **Inspection surfaces:** `uv run python -c "from helm_orchestration import StubCalendarSystemAdapter, StubTaskSystemAdapter; print('ok')"` confirms importability. `rg "helm_connectors" apps/ packages/ tests/ -t py` confirms no lingering references.
- **Failure visibility:** If any import site is missed, pytest collection fails immediately with `ModuleNotFoundError: No module named 'helm_connectors'`. This surfaces the specific test file and line, making the fix obvious.
- **Redaction constraints:** No secrets, credentials, or PII involved. Stub classes hold only in-memory dictionaries of test fixture data.

## Integration Closure

- Upstream surfaces consumed: `StubCalendarSystemAdapter` + `StubTaskSystemAdapter` from `packages/connectors/`; `CalendarProvider` + `InboxProvider` from `packages/providers/protocols.py` (already complete)
- New wiring introduced in this slice: `helm_orchestration.stubs` module with re-exports from `helm_orchestration/__init__.py`
- What remains before the milestone is truly usable end-to-end: UAT verification (`/task`, `/agenda`, email triage cycle via Telegram)

## Tasks

- [x] **T01: Move stubs to orchestration, update all imports, delete packages/connectors** `est:25m`
  - Why: The two stub classes are the only remaining content in `packages/connectors/`. Moving them to `helm_orchestration` (where they naturally belong, since they import `helm_orchestration.schemas`) and updating all import sites is the core migration work. The two e2e test files that import `helm_connectors.google_calendar` (a deleted module) must go first to unblock test collection.
  - Files: `tests/e2e/test_weekly_scheduling_calendar_e2e.py`, `tests/e2e/test_weekly_scheduling_full_stack_e2e.py`, `packages/connectors/` (entire directory), `packages/orchestration/src/helm_orchestration/stubs.py` (new), `packages/orchestration/src/helm_orchestration/__init__.py`, `apps/worker/src/helm_worker/jobs/workflow_runs.py`, `apps/api/src/helm_api/services/workflow_status_service.py`, `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`, `tests/unit/test_workflow_orchestration_service.py`, `tests/integration/test_drift_detection_and_reconciliation.py`, `tests/integration/test_drift_recovery_actions_in_workflow_status.py`, `tests/integration/test_drift_recovery_workflows.py`, `tests/integration/test_weekly_scheduling_end_to_end.py`, `tests/integration/test_weekly_scheduling_with_drift_recovery.py`, `tests/integration/test_workflow_status_routes.py`, `pyproject.toml`
  - Do: (1) Delete the two e2e test files. (2) Create `packages/orchestration/src/helm_orchestration/stubs.py` by copying `StubCalendarSystemAdapter` from `calendar_system.py` and `StubTaskSystemAdapter` from `task_system.py` verbatim — keep `from __future__ import annotations`, `TYPE_CHECKING` guards, and lazy local imports from `helm_orchestration.schemas`. (3) Add `StubCalendarSystemAdapter` and `StubTaskSystemAdapter` to `helm_orchestration/__init__.py` imports and `__all__`. (4) Update all 10 import sites (3 production, 7 test files) from `from helm_connectors import ...` to `from helm_orchestration import ...`. The multi-line import in `test_weekly_scheduling_with_drift_recovery.py` (lines 29-31) needs special attention. (5) Delete `packages/connectors/` directory entirely (`rm -rf`). (6) Remove `"packages/connectors/src"` from `pyproject.toml` line 48.
  - Verify: `rg "helm_connectors" apps/ packages/ tests/ -t py` → zero results; `test ! -d packages/connectors`; `uv run python -c "from helm_orchestration import StubCalendarSystemAdapter, StubTaskSystemAdapter; print('ok')"` → ok
  - Done when: Zero `helm_connectors` imports in Python source; `packages/connectors/` directory gone; stubs importable from `helm_orchestration`

- [x] **T02: Fix pre-existing test failures and verify scripts/test.sh green** `est:15m`
  - Why: 5 unit tests fail because `workflow_runs.run()` calls `_resolve_bootstrap_user_id` which requires `TELEGRAM_ALLOWED_USER_ID` env var. These pre-existing failures (from S03) must be fixed to meet the milestone "all tests green" criterion.
  - Files: `tests/unit/test_worker_notification.py`, `tests/unit/test_worker_registry.py`
  - Do: In each of the 4 failing test functions in `test_worker_notification.py` and the 1 failing test in `test_worker_registry.py`, add `monkeypatch.setattr(workflow_runs, "_resolve_bootstrap_user_id", lambda _: 1)` before the `workflow_runs.run(...)` call. This follows D029 (mock `_resolve_bootstrap_user_id` in worker job unit tests). These are unit tests that don't need a real user row — just bypass the lookup. Then run `bash scripts/test.sh` to confirm the full suite is green.
  - Verify: `uv run pytest tests/unit/test_worker_notification.py tests/unit/test_worker_registry.py -v` → 7 passed; `bash scripts/test.sh` → 0 failures
  - Done when: `scripts/test.sh` exits 0 with no failures

## Files Likely Touched

- `tests/e2e/test_weekly_scheduling_calendar_e2e.py` (deleted)
- `tests/e2e/test_weekly_scheduling_full_stack_e2e.py` (deleted)
- `packages/connectors/` (entire directory deleted)
- `packages/orchestration/src/helm_orchestration/stubs.py` (new)
- `packages/orchestration/src/helm_orchestration/__init__.py`
- `apps/worker/src/helm_worker/jobs/workflow_runs.py`
- `apps/api/src/helm_api/services/workflow_status_service.py`
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py`
- `tests/unit/test_workflow_orchestration_service.py`
- `tests/integration/test_drift_detection_and_reconciliation.py`
- `tests/integration/test_drift_recovery_actions_in_workflow_status.py`
- `tests/integration/test_drift_recovery_workflows.py`
- `tests/integration/test_weekly_scheduling_end_to_end.py`
- `tests/integration/test_weekly_scheduling_with_drift_recovery.py`
- `tests/integration/test_workflow_status_routes.py`
- `tests/unit/test_worker_notification.py`
- `tests/unit/test_worker_registry.py`
- `pyproject.toml`
