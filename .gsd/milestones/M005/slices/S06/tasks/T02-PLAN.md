---
estimated_steps: 3
estimated_files: 2
---

# T02: Fix pre-existing test failures and verify scripts/test.sh green

**Slice:** S06 — Delete packages/connectors + Protocol Finalization
**Milestone:** M005

## Description

Five unit tests fail because `workflow_runs.run()` calls `_resolve_bootstrap_user_id(session)` which raises `RuntimeError("Bootstrap user not found: TELEGRAM_ALLOWED_USER_ID env var is not set")`. These are pre-existing failures introduced by S03/T01 and documented in D029. The fix is to mock `_resolve_bootstrap_user_id` to return a user ID of `1`, bypassing the env var and DB lookup entirely. These are unit tests — they don't need a real user row, just need the function to not raise.

After fixing, run `scripts/test.sh` to confirm the full CI suite is green, satisfying the milestone's "all tests pass" criterion.

## Steps

1. **Fix `tests/unit/test_worker_notification.py`** — 4 failing tests:
   - `test_notification_fires_for_needs_action_true`
   - `test_no_notification_for_needs_action_false`
   - `test_notification_failure_does_not_crash_loop`
   - `test_proposal_summary_extracted_from_artifact`
   
   In each test function, add this line before the `workflow_runs.run(...)` call:
   ```python
   monkeypatch.setattr(workflow_runs, "_resolve_bootstrap_user_id", lambda _: 1)
   ```
   
   Each test already has `monkeypatch: pytest.MonkeyPatch` as a parameter. The `workflow_runs` module is already imported at the top of the file (verify by checking the imports). If `workflow_runs` is not imported, add `from helm_worker.jobs import workflow_runs` at the top.

2. **Fix `tests/unit/test_worker_registry.py`** — 1 failing test:
   - `test_workflow_runs_job_resumes_runnable_runs`
   
   Same fix: add `monkeypatch.setattr(workflow_runs, "_resolve_bootstrap_user_id", lambda _: 1)` before the `workflow_runs.run(...)` call. Verify `workflow_runs` is imported. If the test function uses a different import path (e.g., `from helm_worker.jobs import workflow_runs`), match that.

3. **Run `scripts/test.sh` and verify 0 failures:**
   ```bash
   bash scripts/test.sh
   ```
   This runs `uv run --frozen --extra dev pytest` with the standard ignore list. All tests should pass. If any failures appear that are NOT the 5 `_resolve_bootstrap_user_id` failures, investigate and fix — they may be fallout from T01's import changes.

## Must-Haves

- [ ] All 4 tests in `test_worker_notification.py` pass
- [ ] `test_workflow_runs_job_resumes_runnable_runs` in `test_worker_registry.py` passes
- [ ] `scripts/test.sh` exits 0 with no failures

## Verification

- `uv run pytest tests/unit/test_worker_notification.py tests/unit/test_worker_registry.py -v` → 7 passed, 0 failed
- `bash scripts/test.sh` → exits 0, output shows no FAILED tests
- `uv run ruff check tests/unit/test_worker_notification.py tests/unit/test_worker_registry.py` → 0 errors

## Inputs

- T01 must be complete (all `helm_connectors` imports updated to `helm_orchestration`)
- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — contains `_resolve_bootstrap_user_id` function that raises when `TELEGRAM_ALLOWED_USER_ID` is unset
- D029: "Mock all three of `_resolve_bootstrap_user_id`, `SessionLocal`, and `_build_*_provider` together in worker job unit tests" — for these unit tests, only `_resolve_bootstrap_user_id` is needed because the tests already mock `SessionLocal` and don't construct a provider

## Expected Output

- `tests/unit/test_worker_notification.py` — 4 test functions updated with `monkeypatch.setattr` line
- `tests/unit/test_worker_registry.py` — 1 test function updated with `monkeypatch.setattr` line
- `scripts/test.sh` — green (0 failures)

## Observability Impact

No new runtime signals are introduced by this task — it's test-only changes. The existing observability signals are unchanged:

- **Inspection surface:** `uv run pytest tests/unit/test_worker_notification.py tests/unit/test_worker_registry.py -v` is the canonical health signal. 7 passed = fix is working.
- **scripts/test.sh skip behavior:** When run without `HELM_E2E=true`, the `tests/e2e/conftest.py` hook applies a global skip marker to all collected items. This produces `441 skipped, exit 0` — which is CI green by design. This is pre-existing behavior, not a test failure.
- **Failure visibility:** If the monkeypatch is absent or wrong, pytest produces `RuntimeError: Bootstrap user not found: TELEGRAM_ALLOWED_USER_ID env var is not set` — immediately identifying the missing mock.
- **Redaction constraints:** No secrets involved; mocked user IDs are fixed integers (1).
