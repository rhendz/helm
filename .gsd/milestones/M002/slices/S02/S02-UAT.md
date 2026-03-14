# S02: Repo cleanup and deprecation enforcement — UAT

**Milestone:** M002
**Written:** 2026-03-13

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: This slice only trims deprecated/aspirational repo surfaces and aligns tests/CI and diagnostics with the workflow-engine truth set; no new runtime features or operator flows were added. Verifying tests, static checks, and diagnostic commands is enough to prove behavior.

## Preconditions

- Python toolchain and uv installed (matching scripts/test.sh expectations).
- Project dependencies installed via `uv sync` (or equivalent) with `dev` extras available.
- Current working directory is the repo root.
- Local Postgres is available if integration tests expect a database (same assumptions as M001/M002 test setup).

## Smoke Test

Run the primary test entrypoint and confirm the suite passes:

```bash
bash scripts/test.sh
```

**Expected:**
- uv runs pytest across tests/unit and tests/integration.
- All tests pass with exit code 0.
- No import errors related to `helm_domain`, LinkedIn, or Night Runner paths.

## Test Cases

### 1. Deprecated domain package is quarantined and non-importable

1. Run:
   ```bash
   rg "helm_domain" . || true
   ```
2. **Expected:**
   - No matches in the tree (empty output).
   - If any matches appear, they should only be inside `docs/archive/packages-domain/` or other archived docs, not in `apps/`, `packages/`, `scripts/`, or `tests/`.

3. Attempt a compile-all pass:
   ```bash
   python3 -m compileall .
   ```
4. **Expected:**
   - Command completes successfully.
   - No `ModuleNotFoundError` or similar errors referencing `helm_domain` or `packages.domain`.

### 2. Night Runner surfaces are quarantined or clearly deprecated

1. Run:
   ```bash
   rg "night runner" .
   rg "Night Runner" .
   ```
2. **Expected:**
   - Matches are limited to:
     - `scripts/night-runner.sh`
     - `scripts/install-night-runner-cron.sh`
     - `docs/archive/night-runner.md`
     - `docs/archive/night-runner-prompt.md`
     - Historical references in `docs/internal/helm-v1.md`.
   - `docs/internal/helm-v1.md` references clearly mark Night Runner as deprecated and point to `docs/archive/night-runner.md`.

3. Open `docs/archive/night-runner.md` and `docs/archive/night-runner-prompt.md` (inspection, no command required).
4. **Expected:**
   - Both files read as archived/historical docs, not active product specs.
   - `docs/archive/night-runner.md` references `scripts/night-runner.sh` and `docs/archive/night-runner-prompt.md` rather than any live runbook path under `docs/runbooks/`.

### 3. LinkedIn has no live implementation

1. Run:
   ```bash
   rg "linkedin" . || true
   ```
2. **Expected:**
   - No matches in code, tests, or scripts.
   - Any matches that do appear should be limited to classification or design docs (for example `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md`) describing LinkedIn as a deprecated/remove path, not implementation code.

### 4. Email/Study remain non-truth but wired and tested

1. Run the test suite explicitly (if not already done in the smoke test):
   ```bash
   uv run --frozen --extra dev pytest -q tests/unit tests/integration
   ```
2. **Expected:**
   - All tests pass.
   - `tests/unit/test_replay_queue.py` passes, confirming that `apps/worker/src/helm_worker/jobs/replay.py` is correctly wired to `build_email_agent_runtime`.

3. Run:
   ```bash
   rg "EmailAgent|StudyAgent" .
   ```
4. **Expected:**
   - Matches appear in:
     - Email runtime and storage modules (agents/runtime, helm_runtime/email_agent, storage models/repositories).
     - Worker jobs (`email_message_ingest.py`, `replay.py`).
     - Tests (`tests/unit/test_storage_repositories.py`, `tests/unit/test_email_followup.py`, and replay-related tests).
     - Docs already classified as deprecated or frozen.
   - No new planning/spec or product-defining docs for Email/Study beyond what is already marked deprecated/frozen in the classification inventory.

5. Inspect `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md`.
6. **Expected:**
   - EmailAgent surfaces are tagged as `deprecate` (runtime/worker) or `keep` (storage contracts) as described in T01/T03 summaries.
   - StudyAgent surfaces are tagged as `freeze`.

### 5. CI wiring focuses on workflow-engine truth set

1. Inspect `scripts/test.sh`.
2. **Expected:**
   - Script runs `uv run --frozen --extra dev pytest` (optionally with `-q tests/unit tests/integration`).
   - No explicit references to Night Runner, LinkedIn, or domain-layer test modules.

3. Inspect `.github/workflows/python-checks-reusable.yml`.
4. **Expected:**
   - Workflow invokes `bash scripts/test.sh` and `bash scripts/lint.sh`.
   - No references to removed/quarantined apps or deprecated tests.

## Edge Cases

### Email replay worker injection

1. Open `apps/worker/src/helm_worker/jobs/replay.py` and `tests/unit/test_replay_queue.py`.
2. **Expected:**
   - replay.py imports `build_email_agent_runtime` from `helm_runtime.email_agent` and passes it as `runtime_factory` into `run_replay_queue`.
   - `test_replay_queue.py` monkeypatches or otherwise uses `build_email_agent_runtime` to validate replay behavior for failed email triage runs.
   - The test remains green under the main test command.

### Domain archive accidentally reintroduced into PYTHONPATH

1. Inspect the following scripts:
   - `scripts/new-migration.sh`
   - `scripts/run-worker.sh`
   - `scripts/run-telegram-bot.sh`
   - `scripts/migrate.sh`
   - `scripts/run-api.sh`
2. **Expected:**
   - None of these scripts add `packages/domain/src` to PYTHONPATH.
   - PYTHONPATH additions, if any, reference only active packages.

## Failure Signals

- Any failure in `bash scripts/test.sh` or `uv run --frozen --extra dev pytest -q tests/unit tests/integration`.
- `python3 -m compileall .` emitting `ModuleNotFoundError` (or similar) for `helm_domain`, LinkedIn, or other removed/quarantined modules.
- `rg "helm_domain" .` returning matches outside `docs/archive/packages-domain/`.
- `rg "night runner" .` returning matches outside scripts and archived docs, especially in active runbooks under `docs/runbooks/`.
- `rg "linkedin" .` returning matches in live code, tests, or scripts.
- `tests/unit/test_replay_queue.py` failing, indicating a regression in replay wiring or email runtime injection.
- `.github/workflows/python-checks-reusable.yml` or `scripts/test.sh` referencing removed or quarantined test paths.

## Requirements Proved By This UAT

- R002 — Repo working set is reduced to active and frozen truth: Verified by absence of `helm_domain` imports, confinement of Night Runner to scripts/archive, no live LinkedIn code, and green test suite.
- R004 — Non-core agents do not define current truth: Verified by Email/Study remaining present but constrained to runtime/storage and replay behavior, with tests and docs treating them as deprecated/frozen.
- R005 — Deprecated paths are clearly marked and removed where safe: Verified by classification inventory, archive locations, and rg checks confirming deprecated surfaces are labeled and not treated as live code.

## Not Proven By This UAT

- R003 — Task/calendar workflows remain intact and verified after cleanup: Full end-to-end workflow verification via API/worker/Telegram is covered by S03, not this slice.
- Operational behavior under long-running or failure-heavy loads: This UAT does not stress-test runtime behavior beyond the existing pytest suite.

## Notes for Tester

- This UAT is best run after a clean `uv sync` so that the test environment matches CI.
- If you see new rg matches for deprecated surfaces (LinkedIn, Night Runner, helm_domain), cross-check `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` to decide whether they are intentional new references or regressions.
- Failures in email-related tests usually indicate wiring issues (for example replay runtime injection) rather than truth-set violations; fix wiring first, then re-check that EmailAgent remains non-truth in docs and inventory.
