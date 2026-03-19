---
estimated_steps: 6
estimated_files: 16
---

# T01: Move stubs to orchestration, update all imports, delete packages/connectors

**Slice:** S06 — Delete packages/connectors + Protocol Finalization
**Milestone:** M005

## Description

The `packages/connectors/` package now contains only two stub classes (`StubCalendarSystemAdapter`, `StubTaskSystemAdapter`) and their package scaffolding. Both `gmail.py` and `google_calendar.py` were deleted in S04/S05. This task moves the stubs to `packages/orchestration/`, updates all 12 import sites, deletes the connector package entirely, and removes it from `pyproject.toml`.

Two e2e test files must be deleted first because they import `helm_connectors.google_calendar` (a deleted module), causing `ImportError` during pytest collection — this blocks the entire test suite.

The stubs import `helm_orchestration.schemas` internally (lazy local imports inside methods), so they belong naturally in the orchestration package. No circular import risk.

## Steps

1. **Delete the two e2e test files** that cause collection errors:
   - `rm tests/e2e/test_weekly_scheduling_calendar_e2e.py`
   - `rm tests/e2e/test_weekly_scheduling_full_stack_e2e.py`

2. **Create `packages/orchestration/src/helm_orchestration/stubs.py`** by combining the contents of:
   - `packages/connectors/src/helm_connectors/calendar_system.py` → `StubCalendarSystemAdapter`
   - `packages/connectors/src/helm_connectors/task_system.py` → `StubTaskSystemAdapter`
   
   The new file must:
   - Keep `from __future__ import annotations` at top
   - Keep `TYPE_CHECKING` guard with the type imports from `helm_orchestration.schemas`
   - Keep all lazy local imports inside methods (e.g., `from helm_orchestration.schemas import CalendarSyncResult, ...`)
   - Combine both classes into one file
   - Add `__all__ = ["StubCalendarSystemAdapter", "StubTaskSystemAdapter"]`

3. **Update `packages/orchestration/src/helm_orchestration/__init__.py`**:
   - Add import: `from helm_orchestration.stubs import StubCalendarSystemAdapter, StubTaskSystemAdapter`
   - Add both names to the `__all__` list (alphabetical order)

4. **Update all 12 import sites** — change `from helm_connectors import ...` to `from helm_orchestration import ...`:

   **Production code (3 files):**
   - `apps/worker/src/helm_worker/jobs/workflow_runs.py` line 8: `from helm_connectors import StubTaskSystemAdapter` → `from helm_orchestration import StubTaskSystemAdapter`
   - `apps/api/src/helm_api/services/workflow_status_service.py` lines 8-10: `from helm_connectors import (StubCalendarSystemAdapter, StubTaskSystemAdapter,)` → `from helm_orchestration import StubCalendarSystemAdapter, StubTaskSystemAdapter`
   - `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py` line 14: `from helm_connectors import StubTaskSystemAdapter` → `from helm_orchestration import StubTaskSystemAdapter`

   **Test files (7 files):**
   - `tests/unit/test_workflow_orchestration_service.py` line 2: swap import
   - `tests/integration/test_drift_detection_and_reconciliation.py` line ~17: swap import
   - `tests/integration/test_drift_recovery_actions_in_workflow_status.py` line ~8: swap import
   - `tests/integration/test_drift_recovery_workflows.py` line ~17: swap import
   - `tests/integration/test_weekly_scheduling_end_to_end.py` line ~24: swap import
   - `tests/integration/test_weekly_scheduling_with_drift_recovery.py` lines ~29-31: **multi-line import** — this imports `StubCalendarSystemAdapter` and `StubTaskSystemAdapter` from `helm_connectors` in a parenthesized block. Replace the entire `from helm_connectors import (...)` block with `from helm_orchestration import StubCalendarSystemAdapter, StubTaskSystemAdapter`
   - `tests/integration/test_workflow_status_routes.py` line ~10: swap import

   **Important:** Read each file before editing to get the exact import text. The multi-line import in `test_weekly_scheduling_with_drift_recovery.py` is especially sensitive — get the exact whitespace.

5. **Delete `packages/connectors/` entirely:**
   ```bash
   rm -rf packages/connectors
   ```
   This removes all `.py` files, `__pycache__/`, and any other files in the directory.

6. **Update `pyproject.toml`** — remove line 48 (`"packages/connectors/src",`) from the `[tool.setuptools.packages.find].where` array.

## Observability Impact

This task performs import hygiene with no new runtime behavior. Observable signals:

- **Import success/failure:** `uv run python -c "from helm_orchestration import StubCalendarSystemAdapter, StubTaskSystemAdapter"` is the primary health signal post-migration. `ModuleNotFoundError` means an import site or `__init__.py` update was missed.
- **Test collection errors surface missed imports immediately:** If any of the 10 files still reference `helm_connectors`, pytest fails at collection time with a clear `ModuleNotFoundError`, pinpointing the file. No silent failures.
- **`packages/connectors/` absence:** `test ! -d packages/connectors` confirms the directory was deleted. Presence would indicate the `rm -rf` step was skipped.
- **`pyproject.toml` hygiene:** The removed `packages/connectors/src` entry has no runtime impact (the package is deleted), but its absence keeps the build configuration clean and prevents confusing "no packages found" warnings on future `uv sync` runs.

## Must-Haves

- [ ] `packages/orchestration/src/helm_orchestration/stubs.py` exists with both stub classes
- [ ] `StubCalendarSystemAdapter` and `StubTaskSystemAdapter` importable from `helm_orchestration`
- [ ] All 12 import sites updated (3 production, 7 test, 2 e2e deleted)
- [ ] `packages/connectors/` directory does not exist
- [ ] `pyproject.toml` does not reference `packages/connectors/src`
- [ ] `rg "helm_connectors" apps/ packages/ tests/ -t py` returns zero results

## Verification

- `rg "helm_connectors" apps/ packages/ tests/ -t py` → zero results (note: `helm_providers/gmail.py` has `helm_connectors` in comments/docstrings — these are acceptable and will show if you omit `-t py` or search differently, but the grep for `.py` import lines should be zero)
- `test ! -d packages/connectors && echo "deleted"` → prints "deleted"
- `uv run python -c "from helm_orchestration import StubCalendarSystemAdapter, StubTaskSystemAdapter; print('ok')"` → prints "ok"
- `uv run python -c "from helm_connectors import StubCalendarSystemAdapter" 2>&1` → `ModuleNotFoundError`
- `uv run python -c "from helm_providers import CalendarProvider, InboxProvider; print('ok')"` → prints "ok"
- `uv run ruff check apps/worker/src/helm_worker/jobs/workflow_runs.py apps/api/src/helm_api/services/workflow_status_service.py apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py packages/orchestration/src/helm_orchestration/stubs.py packages/orchestration/src/helm_orchestration/__init__.py` → 0 errors

## Inputs

- `packages/connectors/src/helm_connectors/calendar_system.py` — source for `StubCalendarSystemAdapter` (copy verbatim)
- `packages/connectors/src/helm_connectors/task_system.py` — source for `StubTaskSystemAdapter` (copy verbatim)
- `packages/orchestration/src/helm_orchestration/__init__.py` — add imports and `__all__` entries
- S04 summary: connectors `__init__.py` exports only stubs; `google_calendar.py` already deleted
- S05 summary: `gmail.py` already deleted; connectors directory is "half-empty"

## Expected Output

- `packages/orchestration/src/helm_orchestration/stubs.py` — new file with both stub classes
- `packages/orchestration/src/helm_orchestration/__init__.py` — updated with stub imports/exports
- `packages/connectors/` — deleted
- `pyproject.toml` — `packages/connectors/src` line removed
- 10 files with updated imports (3 production, 7 test)
- 2 e2e test files deleted
