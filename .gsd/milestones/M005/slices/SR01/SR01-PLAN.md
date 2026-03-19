# SR01: Fix test_email_ingest_service.py monkeypatch targets

**Goal:** Fix the 3 broken monkeypatch targets in `test_email_ingest_service.py` so the test file passes and the full unit/integration suite has 0 new failures.
**Demo:** `uv run pytest tests/unit/test_email_ingest_service.py -v` → 3 passed; `uv run pytest tests/unit/ tests/integration/ --ignore=tests/unit/test_study_agent_mvp.py` → 0 failures.

## Must-Haves

- All three `monkeypatch.setattr` calls in `test_email_ingest_service.py` target `"_pull_new_messages_manual"` instead of the deleted `"pull_new_messages_report"`
- All 3 tests in the file pass
- No regressions in the broader unit/integration suite

## Verification

- `uv run pytest tests/unit/test_email_ingest_service.py -v` → 3 passed
- `uv run pytest tests/unit/ tests/integration/ --ignore=tests/unit/test_study_agent_mvp.py` → 0 failures
- `uv run ruff check tests/unit/test_email_ingest_service.py` → All checks passed

## Tasks

- [x] **T01: Update monkeypatch targets from pull_new_messages_report to _pull_new_messages_manual** `est:5m`
  - Why: S05 renamed the module-level function in `email_service.py` but didn't update the test file's monkeypatch targets, causing 3 `AttributeError` failures.
  - Files: `tests/unit/test_email_ingest_service.py`
  - Do: Replace all 3 occurrences of `"pull_new_messages_report"` with `"_pull_new_messages_manual"` in `monkeypatch.setattr` calls. No logic or signature changes needed — the lambda signatures already match.
  - Verify: `uv run pytest tests/unit/test_email_ingest_service.py -v` → 3 passed; `uv run pytest tests/unit/ tests/integration/ --ignore=tests/unit/test_study_agent_mvp.py` → 0 failures; `uv run ruff check tests/unit/test_email_ingest_service.py` → clean.
  - Done when: All 3 tests pass and the broader suite shows no new failures.

## Files Likely Touched

- `tests/unit/test_email_ingest_service.py`

## Observability / Diagnostics

This slice changes test code only — no runtime signals or production log paths are affected. Failure visibility: broken monkeypatch targets surface immediately as `AttributeError: <module 'helm_api.services.email_service'> does not have attribute '<name>'` in the pytest run output, making staleness easy to diagnose. Diagnostic command: `uv run pytest tests/unit/test_email_ingest_service.py -v`. No structured log changes, no redaction constraints, no new failure artifacts.
