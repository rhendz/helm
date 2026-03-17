---
estimated_steps: 3
estimated_files: 1
---

# T01: Move misclassified calendar adapter test to unit layer

**Slice:** S05 — Strict test boundaries and real E2E calendar coverage
**Milestone:** M004

## Description

`tests/integration/test_google_calendar_adapter_real_api.py` has 98 Mock/patch calls and zero real API calls — despite its name suggesting "real API", it is entirely a unit test. This violates R113's test layer separation policy (D007). Move it to `tests/unit/test_google_calendar_adapter.py` and verify it passes.

This is a zero-risk file move with no code changes inside the file.

## Steps

1. **Move the file:**
   ```bash
   cd /Users/ankush/git/helm
   git mv tests/integration/test_google_calendar_adapter_real_api.py tests/unit/test_google_calendar_adapter.py
   ```

2. **Verify no other file references the old path:**
   ```bash
   grep -r "test_google_calendar_adapter_real_api" tests/ --include="*.py"
   grep -r "test_google_calendar_adapter_real_api" .github/ --include="*.yml" --include="*.yaml" 2>/dev/null
   ```
   If any references exist, update them to the new path.

3. **Run the moved file from its new location and the full test suite:**
   ```bash
   OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/unit/test_google_calendar_adapter.py -v
   OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/unit/ tests/integration/ --ignore=tests/unit/test_study_agent_mvp.py -q
   ```

## Must-Haves

- [ ] File moved from `tests/integration/test_google_calendar_adapter_real_api.py` to `tests/unit/test_google_calendar_adapter.py`
- [ ] All tests in the moved file pass from the new location
- [ ] No references to the old file path remain in the codebase
- [ ] Full unit + integration suite passes (no regressions)

## Verification

- `ls tests/integration/test_google_calendar_adapter_real_api.py` → file not found
- `ls tests/unit/test_google_calendar_adapter.py` → file exists
- `OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/unit/test_google_calendar_adapter.py -v` → all tests pass
- `OPERATOR_TIMEZONE=America/Los_Angeles uv run --frozen --extra dev pytest tests/unit/ tests/integration/ --ignore=tests/unit/test_study_agent_mvp.py -q` → no regressions

## Inputs

- `tests/integration/test_google_calendar_adapter_real_api.py` — 749-line test file with 98 Mock calls, zero real API calls

## Expected Output

- `tests/unit/test_google_calendar_adapter.py` — same file, new location, all tests passing
