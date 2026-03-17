---
estimated_steps: 5
estimated_files: 5
---

# T02: Add watchfiles live reload and ddtrace APM instrumentation

**Slice:** S06 — Dev experience, observability, and cleanup
**Milestone:** M004

## Description

Add developer experience improvements (live reload for worker and telegram-bot) and observability (Datadog APM traces on the `/task` path). These are additive changes — no existing behavior is modified.

Live reload uses `watchfiles` (per D010). Datadog uses `ddtrace` (per D009). Both are dev dependencies. APM spans are no-ops without a DD agent running — safe to ship unconditionally.

## Steps

1. **Add `watchfiles` and `ddtrace` to dev dependencies.** In `pyproject.toml`, add `"watchfiles>=0.21.0"` and `"ddtrace>=2.0.0"` to the `[project.optional-dependencies].dev` list (after the existing entries like `ruff`). Run `uv lock` to update the lockfile (if `uv.lock` exists) or just verify the edit is correct.

2. **Update `scripts/run-worker.sh` for live reload.** Change the last line from:
   ```
   python -m helm_worker.main
   ```
   to:
   ```
   python -m watchfiles --filter python helm_worker.main apps/worker/src packages/
   ```
   Keep the existing `PYTHONPATH` export and `set -euo pipefail` unchanged.

3. **Update `scripts/run-telegram-bot.sh` for live reload.** Same pattern — change the last line from:
   ```
   python -m helm_telegram_bot.main
   ```
   to:
   ```
   python -m watchfiles --filter python helm_telegram_bot.main apps/telegram-bot/src packages/
   ```

4. **Add ddtrace APM spans to `apps/telegram-bot/src/helm_telegram_bot/commands/task.py`.** At the top of the file, add:
   ```python
   from ddtrace import tracer
   ```
   Then wrap the main work in `_run_task_async` with a span. Find the function `_run_task_async` and:
   - Add `with tracer.trace("helm.task.run", resource="task_quick_add"):` around the entire function body (inside the try/except)
   - Add `with tracer.trace("helm.task.inference", resource="infer_task_semantics"):` specifically around the `run_in_executor` call that invokes `infer_task_semantics`
   
   The `tracer.trace()` context manager is a no-op when no DD agent is connected — no guard needed.

5. **Add DD env vars to `.env.example`.** Append these lines:
   ```
   # Datadog (optional — APM traces)
   DD_ENV=development
   DD_SERVICE=helm
   DD_VERSION=0.4.0
   ```

6. **Commit.** `git add -A && git commit -m "feat(S06/T02): Add watchfiles live reload and ddtrace APM instrumentation"`

## Must-Haves

- [ ] `watchfiles>=0.21.0` in pyproject.toml dev deps
- [ ] `ddtrace>=2.0.0` in pyproject.toml dev deps
- [ ] `run-worker.sh` uses `python -m watchfiles --filter python helm_worker.main`
- [ ] `run-telegram-bot.sh` uses `python -m watchfiles --filter python helm_telegram_bot.main`
- [ ] `task.py` has `from ddtrace import tracer` and span wrappers on `_run_task_async` and inference call
- [ ] `.env.example` has DD_ENV, DD_SERVICE, DD_VERSION

## Verification

- `grep "watchfiles" pyproject.toml` → shows `watchfiles>=0.21.0`
- `grep "ddtrace" pyproject.toml` → shows `ddtrace>=2.0.0`
- `grep "watchfiles" scripts/run-worker.sh` → shows the watchfiles command
- `grep "watchfiles" scripts/run-telegram-bot.sh` → shows the watchfiles command
- `grep "tracer.trace" apps/telegram-bot/src/helm_telegram_bot/commands/task.py` → shows span wrappers
- `grep "DD_ENV\|DD_SERVICE\|DD_VERSION" .env.example` → shows all three
- Existing tests still pass (run: `uv run --frozen pytest tests/unit/ tests/integration/ --ignore=tests/integration/test_study_agent_mvp.py --ignore=tests/unit/test_study_agent_mvp.py -q`)

## Inputs

- T01 completed: `milestone/M004` merged into `main`, `task.py` exists at `apps/telegram-bot/src/helm_telegram_bot/commands/task.py`
- D009 decision: `ddtrace` for APM
- D010 decision: `watchfiles` for live reload
- Current `pyproject.toml` dev deps list starts at line 25
- Current `run-worker.sh` and `run-telegram-bot.sh` use `python -m <module>.main` as last line

## Expected Output

- `pyproject.toml` — dev deps include `watchfiles` and `ddtrace`
- `scripts/run-worker.sh` — uses watchfiles for reload
- `scripts/run-telegram-bot.sh` — uses watchfiles for reload
- `apps/telegram-bot/src/helm_telegram_bot/commands/task.py` — has ddtrace span wrappers
- `.env.example` — has DD configuration vars
