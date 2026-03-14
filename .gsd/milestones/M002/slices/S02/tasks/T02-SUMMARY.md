---
id: T02
parent: S02
milestone: M002
provides:
  - Deprecated LinkedIn/Night Runner/domain artifacts quarantined or updated per inventory
  - Updated docs and classification inventory reflecting quarantined status
key_files:
  - .gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md
  - docs/internal/helm-v1.md
  - docs/archive/night-runner.md
  - docs/archive/night-runner-prompt.md
  - docs/archive/packages-domain/
  - scripts/night-runner.sh
  - scripts/install-night-runner-cron.sh
  - scripts/new-migration.sh
  - scripts/run-worker.sh
  - scripts/run-telegram-bot.sh
  - scripts/migrate.sh
  - scripts/run-api.sh
key_decisions:
  - packages/domain is physically moved under docs/archive/packages-domain as a quarantined design reference; no live code imports helm_domain.
  - Night Runner runbooks are quarantined under docs/archive while scripts remain runnable but are treated as deprecated tooling.
  - LinkedIn remains a logical-only deprecate/remove entry; no concrete LinkedIn code or tests exist in the tree.
patterns_established:
  - Quarantine deprecated packages under docs/archive/ instead of leaving them in importable namespaces.
  - Treat helm-v1 domain and night-runner sections as historical design references, not live implementation contracts.
observability_surfaces:
  - rg "night runner|night-runner" .
  - rg "helm_domain" .
  - .gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md
  - python3 -m compileall .
  - pytest -q tests/unit tests/integration
duration: ~75m
verification_result: partial
completed_at: 2026-03-13T21:56:00-07:00
blocker_discovered: false
---

# T02: Physically remove or quarantine LinkedIn, Night Runner, and domain layer artifacts

## What Happened

- Applied the refined M002 classification inventory to identify concrete LinkedIn, Night Runner, and domain-layer artifacts to remove or quarantine.
- Confirmed via rg that there is no concrete LinkedIn connector or LinkedIn-related code/tests in the tree; LinkedIn remains a logical-only deprecate/remove entry in the inventory.
- Quarantined the aspirational domain package by moving `packages/domain` to `docs/archive/packages-domain` via `git mv`, preserving the code as a design reference while removing it from the importable packages namespace.
- Updated helper scripts (`scripts/new-migration.sh`, `scripts/run-worker.sh`, `scripts/run-telegram-bot.sh`, `scripts/migrate.sh`, `scripts/run-api.sh`) to drop `packages/domain/src` from PYTHONPATH so no runtime flow depends on the quarantined domain layer.
- Quarantined Night Runner runbooks by moving `docs/runbooks/night-runner.md` and `docs/runbooks/night-runner-prompt.md` into `docs/archive/` via `git mv`, keeping them as historical reference only.
- Updated `scripts/night-runner.sh` and the quarantined `docs/archive/night-runner.md` content to reference the new `docs/archive/night-runner-prompt.md` path so the script continues to work if invoked, while clearly living in a deprecated tooling space.
- Edited `docs/internal/helm-v1.md` to:
  - Mark the `packages/domain` entry in the target repo structure as historical, pointing at the `docs/archive/packages-domain/` quarantine location.
  - Annotate the `Domain Model` section as a design reference, clarifying that the current implementation uses storage models rather than the now-quarantined `packages/domain` package.
  - Mark Workstream G (night-runner automation) as deprecated and point to `docs/archive/night-runner.md` for historical context.
- Updated `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` to:
  - Reflect the physical move of `packages/domain` into `docs/archive/packages-domain/` while keeping its status as `quarantine`.
  - Update Night Runner runbook paths from `docs/runbooks/...` to `docs/archive/...` with matching `quarantine` status and rationales.
- Ran `python3 -m compileall .` to catch missing-module errors after the domain move and script updates; the command completed successfully without import errors from removed/quarantined modules.
- Attempted to run `pytest -q tests/unit tests/integration` but `pytest` is not on PATH in this environment, so test verification is deferred to a later run.

## Verification

- `rg "linkedin" .` — no matches; consistent with the inventory note that LinkedIn exists only as a logical deprecate/remove entry and has no concrete code/tests in the tree.
- `rg "helm_domain" .` — no matches; confirms that after moving `packages/domain` under `docs/archive/` there are no remaining imports or references to the domain package in live code, tests, or scripts.
- `rg "night runner|night-runner" .` — matches are limited to:
  - `scripts/night-runner.sh` and `scripts/install-night-runner-cron.sh` (deprecated tooling but still runnable).
  - `docs/archive/night-runner.md` and `docs/archive/night-runner-prompt.md` (quarantined runbooks/prompt).
  - A small number of references in `docs/internal/helm-v1.md` that have been annotated as historical/deprecated and point to the archive path.
- `python3 -m compileall .` — completed successfully, including the quarantined `docs/archive/packages-domain/src/helm_domain` modules, with no missing-module errors from removed paths.
- `pytest -q tests/unit tests/integration` — not executed successfully in this environment (`pytest: command not found`); the command path is documented here so a later run can verify tests once the toolchain is available.

## Deviations

- The task plan anticipated a concrete LinkedIn connector path under `packages/connectors/src/helm/connectors/linkedin`; the refined inventory and rg confirm that no such package exists. Cleanup for LinkedIn in this task is limited to ensuring there are no stray references (none found) and leaving the logical LinkedIn entries in the classification inventory.
- Night Runner scripts (`scripts/night-runner.sh`, `scripts/install-night-runner-cron.sh`) were left in place (per inventory: `deprecate`) but now target quarantined docs under `docs/archive/`; they remain runnable as historical tooling rather than being fully removed.
- Full test verification (`pytest -q tests/unit tests/integration`) could not be run due to missing `pytest` on PATH. `python3 -m compileall .` provides a static import sanity check, but dynamic behavior remains to be re-validated once pytest is available.

## Diagnostics

- To verify quarantine/cleanup state in future slices:
  - Run `rg "helm_domain" .` to confirm the domain package is only present under `docs/archive/packages-domain/` and not imported by live code.
  - Run `rg "night runner" .` and `rg "Night Runner" .` to ensure references are confined to deprecated scripts, archived docs, and annotated historical sections in `docs/internal/helm-v1.md`.
  - Run `rg "linkedin" .` to confirm there is still no concrete LinkedIn implementation.
  - Use `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` as the authoritative list of quarantined/removed artifacts and compare it against rg output.
  - Run `python3 -m compileall .` and `pytest -q tests/unit tests/integration` (via `bash scripts/test.sh` or `uv run --frozen --extra dev pytest -q tests/unit tests/integration`) to catch missing-module or import regressions tied to quarantined paths.

## Known Issues

- Night Runner scripts are still present in `scripts/` and referenced by the archived runbook. They are explicitly classified as deprecated; if future slices decide to remove them entirely, the classification inventory and docs should be updated accordingly.
- The quarantined domain package now lives under `docs/archive/packages-domain/` and is no longer on PYTHONPATH, but `docs/domain/` still contains design content that may reference the domain layer conceptually. These docs are already marked as `quarantine` in the classification inventory.
- Test coverage for surfaces that interacted indirectly with the domain layer (if any existed) has not been re-run due to missing pytest; once the test runner is available, `pytest -q tests/unit tests/integration` should be executed to confirm no regressions.

## Files Created/Modified

- `docs/archive/night-runner.md` — New location for the Night Runner runbook; content updated to reference `docs/archive/night-runner-prompt.md` and scripts under `scripts/`.
- `docs/archive/night-runner-prompt.md` — New location for the Night Runner prompt used by `scripts/night-runner.sh`.
- `docs/archive/packages-domain/` — New quarantine directory holding the former `packages/domain` code as a design reference (including `src/helm_domain/__init__.py` and `models.py`).
- `docs/internal/helm-v1.md` — Updated repo structure and domain model sections to mark the domain package and domain model as historical/design-reference only; annotated Workstream G (night-runner automation) as deprecated and pointed to the archived runbook.
- `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` — Updated entries for `packages/domain` and Night Runner runbooks to reflect their new archived paths and clarified quarantined status.
- `scripts/night-runner.sh` — Updated the default prompt path and usage text to use `docs/archive/night-runner-prompt.md` so the script continues to work against the archived prompt file.
- `scripts/new-migration.sh` — Removed `packages/domain/src` from PYTHONPATH, aligning with the quarantined status of the domain package.
- `scripts/run-worker.sh` — Removed `packages/domain/src` from PYTHONPATH.
- `scripts/run-telegram-bot.sh` — Removed `packages/domain/src` from PYTHONPATH.
- `scripts/migrate.sh` — Removed `packages/domain/src` from PYTHONPATH.
- `scripts/run-api.sh` — Removed `packages/domain/src` from PYTHONPATH.
