---
estimated_steps: 8
estimated_files: 12
---

# T03: Trim deprecated Email/Study artifacts and align tests/CI with the truth set

**Slice:** S02 — Repo cleanup and deprecation enforcement
**Milestone:** M002

## Description

Constrain EmailAgent and StudyAgent to their non-truth-defining roles while keeping them present for this version. Remove or quarantine deprecated planning/spec/docs and non-essential jobs, update tests that currently enforce deprecated email behavior, and adjust CI configs so that the remaining suite focuses on the workflow-engine and task/calendar workflows rather than Email/Study flows.

## Steps

1. Review `.gsd/milestones/M002/M002-TRUTH-NOTE.md`, `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md`, and the updated classification inventory to understand the intended end-state for EmailAgent and StudyAgent (deprecated vs frozen) and which artifacts are tagged deprecate/remove/quarantine.
2. Identify all EmailAgent/StudyAgent-related files and modules, including storage models and repositories, runtime wrappers, worker jobs, docs/runbooks, and tests (e.g., `EmailAgentConfigORM`, `EmailAgentConfigRepository`, `HelmEmailAgentRuntime`, `email_message_ingest`, `test_email_followup`).
3. Decide, in line with the truth note and inventory, which Email/Study artifacts must remain (minimal config/storage/runtime) vs which can be removed or quarantined (planning prompts, runbooks, non-essential jobs, aspirational specs). Update the classification inventory accordingly if adjustments are needed.
4. Remove or quarantine deprecated Email/Study docs, prompts, and non-essential jobs while preserving minimal runtime and storage wiring; ensure imports and entrypoints are updated so the worker/API can still start without referencing removed modules.
5. Refactor or remove tests that enforce deprecated Email behavior (e.g., email follow-up flows) while keeping tests that validate shared storage contracts; adjust them to avoid treating EmailAgent as truth-defining where possible.
6. Inspect CI configuration files (e.g., `.github/workflows/*.yml`, `scripts/test.sh`, `scripts/lint.sh`) for references to removed Email/Study tests or apps and update them to reflect the current test suite.
7. Run `pytest -q tests/unit tests/integration` and the standard local CI commands (e.g., `scripts/test.sh`) to ensure the suite passes and no checks rely on removed Email/Study behavior.
8. Update `docs/internal/helm-v1.md` and the classification inventory to clearly describe EmailAgent as deprecated and StudyAgent as frozen, noting which surfaces remain and which were removed/quarantined in this slice.

## Must-Haves

- [ ] EmailAgent and StudyAgent remain present in the tree with minimal, non-truth-defining runtime/storage/config surfaces as described in the truth note.
- [ ] Tests and CI configs no longer treat Email/Study flows as core truth; any removed Email/Study artifacts are reflected in docs and the classification inventory.

## Verification

- `pytest -q tests/unit tests/integration` passes with Email/Study artifacts present but without tests enforcing deprecated email flows.
- Local CI commands (e.g., `scripts/test.sh` and, if present, GitHub Actions workflow identifiers referenced in docs) run successfully without referencing removed Email/Study tests/apps.
- `rg "EmailAgent|StudyAgent" .` shows only expected runtime/config/storage surfaces and updated docs/inventory, not removed planning/spec surfaces.

## Observability Impact

- Signals added/changed: None directly; this task reduces deprecated behavior and keeps existing runtime logging for Email/Study where retained.
- How a future agent inspects this: Use `pytest` and CI scripts for regression checks, `rg` for Email/Study symbol reachability, and the classification inventory/docs for the intended status of Email/Study surfaces.
- Failure state exposed: Failing tests or CI commands will indicate where Email/Study dependencies were under-trimmed or over-removed; mismatched docs/inventory will highlight classification drift.

## Inputs

- `.gsd/milestones/M002/M002-TRUTH-NOTE.md` and `.gsd/milestones/M002/M002-CLASSIFICATION-RULES.md` — define the non-core status of EmailAgent and StudyAgent.
- `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` — refined Email/Study artifact statuses from T01/T02.
- Email/Study-related code, tests, and docs: `packages/storage/src/helm_storage/models.py`, `packages/storage/src/helm_storage/repositories/email_agent_config.py`, `packages/runtime/src/helm_runtime/email_agent.py`, `apps/worker/src/helm_worker/jobs/email_message_ingest.py`, `tests/unit/test_storage_repositories.py`, `tests/unit/test_email_followup.py`, and related docs.
- CI configs: `.github/workflows/*.yml` and local scripts such as `scripts/test.sh`.

## Expected Output

- A narrowed Email/Study surface that matches the truth note (deprecated/frozen but present), with tests and CI configs aligned to the workflow-engine truth set and all slice-level verification commands passing.
