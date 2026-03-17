---
estimated_steps: 5
estimated_files: 3
---

# T02: Add OPERATOR_TIMEZONE to RuntimeAppSettings and fix test environment

**Slice:** S02 — Timezone correctness and shared scheduling primitives
**Milestone:** M004

## Description

Add `OPERATOR_TIMEZONE` as a required field to `RuntimeAppSettings` with a `field_validator` that validates the IANA timezone string by calling `ZoneInfo(value)` at init time. Since all three apps (`WorkerSettings`, `BotSettings`, `APISettings`) extend `RuntimeAppSettings`, this field is inherited automatically — no per-app changes needed.

Because `OPERATOR_TIMEZONE` has no default, adding it as a required field will break any test that instantiates a settings class without that env var set. Fix this with a `tests/conftest.py` autouse session-scoped fixture that injects `OPERATOR_TIMEZONE=America/Los_Angeles` before test collection. Also update `.env.example` with the new variable.

**Key decisions already made:**
- `OPERATOR_TIMEZONE` is required with no default — fail-fast behavior is desired (D005)
- All three apps inherit via `RuntimeAppSettings` — no per-app special handling needed
- Test fix: `conftest.py` at `tests/` root level with `os.environ` monkeypatch before test session — this is the safest, least-invasive approach

## Steps

1. **Edit `packages/runtime/src/helm_runtime/config.py`** — add the required field and validator:

   ```python
   from __future__ import annotations
   
   from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
   
   from pydantic import field_validator
   from pydantic_settings import BaseSettings, SettingsConfigDict
   
   # ... existing code ...
   
   class RuntimeAppSettings(RuntimeSettings):
       app_env: str = "local"
       log_level: str = "INFO"
       operator_timezone: str  # required — no default; fails fast if unset or invalid
   
       @field_validator("operator_timezone")
       @classmethod
       def validate_operator_timezone(cls, v: str) -> str:
           try:
               ZoneInfo(v)
           except (ZoneInfoNotFoundError, KeyError) as exc:
               raise ValueError(
                   f"OPERATOR_TIMEZONE '{v}' is not a valid IANA timezone string. "
                   f"Example: 'America/Los_Angeles'"
               ) from exc
           return v
   ```

2. **Create `tests/conftest.py`** at the root of the `tests/` directory:

   ```python
   """Root conftest: inject required env vars before any test module imports settings."""
   import os
   
   # Must be set before any settings class is instantiated.
   # All RuntimeAppSettings subclasses (WorkerSettings, BotSettings, APISettings)
   # require OPERATOR_TIMEZONE. Setting it here covers unit and integration tests.
   os.environ.setdefault("OPERATOR_TIMEZONE", "America/Los_Angeles")
   ```

   Use `os.environ.setdefault` (not `os.environ[key] = value`) so that if the real env already has a value (e.g. in CI), it is not overridden.

3. **Edit `.env.example`** — add under the `# Scheduling` section:

   ```
   # Operator local timezone (IANA format). Required. Scheduling fails if unset.
   OPERATOR_TIMEZONE=America/Los_Angeles
   ```

4. **Run verification** to confirm the fix works:
   ```bash
   # All unit tests should pass
   cd /path/to/repo && .venv/bin/python -m pytest tests/unit/ -v
   # All integration tests should pass
   .venv/bin/python -m pytest tests/integration/ -v
   # Confirm invalid TZ raises at init
   .venv/bin/python -c "
   import os; os.environ['OPERATOR_TIMEZONE'] = 'Not/A/Timezone'
   from helm_runtime.config import RuntimeAppSettings
   try:
       s = RuntimeAppSettings()
       print('ERROR: should have raised')
   except Exception as e:
       print('OK, raised:', type(e).__name__)
   "
   ```

5. **Check for any tests that still break** — look for tests that patch or override `OPERATOR_TIMEZONE` explicitly and ensure they still work after `conftest.py` is added. The `conftest.py` `setdefault` pattern ensures tests that set their own value win.

## Must-Haves

- [ ] `RuntimeAppSettings.operator_timezone: str` field added with no default (required)
- [ ] `field_validator` calls `ZoneInfo(v)` and raises `ValueError` with a clear message for invalid IANA strings
- [ ] `tests/conftest.py` exists at `tests/` root, sets `os.environ.setdefault("OPERATOR_TIMEZONE", "America/Los_Angeles")`
- [ ] `OPERATOR_TIMEZONE=America/Los_Angeles` added to `.env.example` with an explanatory comment
- [ ] `pytest tests/unit/ -v` passes with no new failures
- [ ] `pytest tests/integration/ -v` passes with no new failures

## Verification

- `cd /Users/ankush/git/helm/.gsd/worktrees/M004 && .venv/bin/python -m pytest tests/unit/ -v 2>&1 | tail -5` — no failures
- `cd /Users/ankush/git/helm/.gsd/worktrees/M004 && .venv/bin/python -m pytest tests/integration/ -v 2>&1 | tail -5` — no failures
- Invalid timezone test (see step 4) → raises `ValidationError` or `ValueError`
- `grep "OPERATOR_TIMEZONE" /Users/ankush/git/helm/.gsd/worktrees/M004/.env.example` → present

## Observability Impact

- Signals added/changed: invalid `OPERATOR_TIMEZONE` surfaces as a `ValidationError` / `ValueError` at settings instantiation (startup), before any job runs — visible in app logs immediately on boot
- How a future agent inspects this: `python -c "from helm_worker.config import settings; print(settings.operator_timezone)"` — prints the active timezone or fails with a clear error
- Failure state exposed: missing/invalid `OPERATOR_TIMEZONE` is now a hard startup failure rather than a silent wrong-TZ condition

## Inputs

- `packages/runtime/src/helm_runtime/config.py` — existing `RuntimeAppSettings` class; add field + validator
- `.env.example` — existing file; add `OPERATOR_TIMEZONE` to the Scheduling section
- No file at `tests/conftest.py` — create it fresh

## Expected Output

- `packages/runtime/src/helm_runtime/config.py` — `RuntimeAppSettings` with `operator_timezone: str` field and `validate_operator_timezone` class method validator
- `tests/conftest.py` — new file with `os.environ.setdefault("OPERATOR_TIMEZONE", "America/Los_Angeles")`
- `.env.example` — updated Scheduling section with `OPERATOR_TIMEZONE=America/Los_Angeles`
