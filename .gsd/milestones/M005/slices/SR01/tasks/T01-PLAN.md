---
estimated_steps: 3
estimated_files: 1
---

# T01: Update monkeypatch targets from pull_new_messages_report to _pull_new_messages_manual

**Slice:** SR01 — Fix test_email_ingest_service.py monkeypatch targets
**Milestone:** M005

## Description

S05 replaced the `pull_new_messages_report` function in `email_service.py` with `_pull_new_messages_manual` (a private module-level wrapper). The three tests in `test_email_ingest_service.py` still patch the old name, causing `AttributeError`. Fix the monkeypatch target strings.

## Steps

1. Open `tests/unit/test_email_ingest_service.py` and replace every occurrence of `"pull_new_messages_report"` with `"_pull_new_messages_manual"`. There are exactly 3 occurrences, one in each test function's `monkeypatch.setattr` call:
   - `test_ingest_manual_email_messages_normalizes_failures_and_processes_valid` (line ~24)
   - `test_plan_seed_email_messages_returns_bucketed_thread_report` (line ~65)
   - `test_enqueue_seed_email_messages_persists_only_deep_seed_threads` (line ~103)
2. Run `uv run pytest tests/unit/test_email_ingest_service.py -v` — expect 3 passed.
3. Run `uv run pytest tests/unit/ tests/integration/ --ignore=tests/unit/test_study_agent_mvp.py` — expect 0 failures. Run `uv run ruff check tests/unit/test_email_ingest_service.py` — expect clean.

## Must-Haves

- [ ] All three `monkeypatch.setattr` calls target `"_pull_new_messages_manual"`
- [ ] Zero occurrences of `"pull_new_messages_report"` remain in the file
- [ ] All 3 tests pass
- [ ] No regressions in broader suite

## Verification

- `uv run pytest tests/unit/test_email_ingest_service.py -v` → 3 passed
- `uv run pytest tests/unit/ tests/integration/ --ignore=tests/unit/test_study_agent_mvp.py` → 0 failures
- `uv run ruff check tests/unit/test_email_ingest_service.py` → All checks passed

## Inputs

- `tests/unit/test_email_ingest_service.py` — current file with 3 broken `"pull_new_messages_report"` monkeypatch targets
- `apps/api/src/helm_api/services/email_service.py` — production code (do NOT modify); defines `_pull_new_messages_manual` at line 39

## Expected Output

- `tests/unit/test_email_ingest_service.py` — 3 monkeypatch targets updated; all tests green

## Observability Impact

This task modifies test code only — no runtime signals change. Failure visibility: if a future rename of `_pull_new_messages_manual` occurs in production code, the three tests will raise `AttributeError: <module ...> does not have attribute '_pull_new_messages_manual'`, pinpointing the stale monkeypatch target. Inspection surface: `uv run pytest tests/unit/test_email_ingest_service.py -v` is the diagnostic command. No log redaction concerns — test-only change.
