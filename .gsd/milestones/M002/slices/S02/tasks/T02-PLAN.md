---
estimated_steps: 7
estimated_files: 12
---

# T02: Physically remove or quarantine LinkedIn, Night Runner, and domain layer artifacts

**Slice:** S02 — Repo cleanup and deprecation enforcement
**Milestone:** M002

## Description

Use the refined classification inventory to aggressively prune deprecated integrations and aspirational layers: remove or quarantine the LinkedIn connector, Night Runner artifacts, and `packages/domain` while preserving the workflow-engine core. Ensure references, imports, and docs are updated so the repo builds and tests without depending on these paths.

## Steps

1. Review the updated `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` from T01 to confirm which LinkedIn, Night Runner, and `packages/domain` files/modules are tagged for remove vs quarantine.
2. Delete or move to a clearly-named quarantine directory (e.g., `docs/archive/` or `quarantine/`) the LinkedIn connector package (`packages/connectors/src/helm/connectors/linkedin`), Night Runner runbooks and any app/scripts, and the `packages/domain` package or its modules, in line with the inventory.
3. Scan code and tests for imports of removed modules (e.g., `helm.connectors.linkedin`, `helm_domain`) using `rg` and adjust or remove those references where they are purely deprecated; if any reference is used only in tests validating deprecated behavior, mark those tests for deletion or adjustment in this task.
4. Update `docs/internal/helm-v1.md` and any relevant runbooks to remove or rephrase references to LinkedIn, Night Runner, and `packages/domain` as live integrations, pointing instead to their deprecated/quarantined status.
5. Update `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` to reflect actual deletions/quarantine moves, including new paths (e.g., under `docs/archive/`) and confirming that no removed path is still marked keep/freeze.
6. Run `python -m compileall .` (or equivalent static check) to catch missing-module errors introduced by deletions and fix any remaining references.
7. Run `pytest -q tests/unit tests/integration` and adjust or remove any failing tests that depended solely on removed LinkedIn/Night Runner/domain artifacts (keeping tests that protect the workflow-engine core intact).

## Must-Haves

- [ ] LinkedIn connector modules, Night Runner runbooks/apps/scripts, and `packages/domain` are either removed from the tree or relocated under a clearly-labeled quarantine/archive path.
- [ ] No remaining code, tests, or docs treat LinkedIn, Night Runner, or `packages/domain` as live, un-deprecated surfaces; all references are updated or removed.

## Verification

- `rg "linkedin" .`, `rg "night runner|night-runner" .`, and `rg "helm_domain" .` only match within quarantine/archive docs or the classification inventory.
- `python -m compileall .` completes without import errors for removed modules.
- `pytest -q tests/unit tests/integration` passes, or any residual failures clearly relate to Email/Study surfaces to be addressed in T03.

## Observability Impact

- Signals added/changed: None — this task only removes/quarantines deprecated code/docs; it does not alter runtime logging or metrics.
- How a future agent inspects this: Use `rg` for deprecated symbols, `pytest` for regression detection, and `git diff` to see removed/quarantined paths.
- Failure state exposed: Missing-module errors or failing tests will indicate undeclared dependencies on removed artifacts; mismatched inventory entries will show where documentation lags tree changes.

## Inputs

- `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` — refined map from T01 specifying remove vs quarantine for LinkedIn, Night Runner, and domain artifacts.
- `packages/connectors/src/helm/connectors/linkedin/` — LinkedIn connector implementation to remove or quarantine.
- `docs/runbooks/night-runner*.md` and any Night Runner-related apps/scripts — deprecated runbooks/apps.
- `packages/domain/` — domain layer package marked for quarantine/remove.
- `docs/internal/helm-v1.md` — core spec doc that currently mentions deprecated integrations.

## Expected Output

- Removed or quarantined LinkedIn, Night Runner, and `packages/domain` artifacts with updated imports, docs, and classification inventory, and a repo that still builds and tests successfully.
