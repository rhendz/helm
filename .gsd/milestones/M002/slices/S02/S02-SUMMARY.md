---
id: S02
parent: M002
milestone: M002
provides:
  - Deprecated and aspirational surfaces quarantined or updated per truth-set inventory
  - Tests/CI and diagnostics aligned to the workflow-engine core (task/calendar, status, replay)
requires:
  - slice: S01
    provides: Truth note, classification rules, and initial inventory for deprecated surfaces
affects:
  - S03
key_files:
  - .gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md
  - docs/internal/helm-v1.md
  - docs/archive/night-runner.md
  - docs/archive/night-runner-prompt.md
  - docs/archive/packages-domain/
  - apps/worker/src/helm_worker/jobs/replay.py
  - scripts/night-runner.sh
  - scripts/install-night-runner-cron.sh
  - scripts/new-migration.sh
  - scripts/run-worker.sh
  - scripts/run-telegram-bot.sh
  - scripts/migrate.sh
  - scripts/run-api.sh
  - scripts/test.sh
  - .github/workflows/python-checks-reusable.yml
key_decisions:
  - packages/domain is quarantined under docs/archive/packages-domain as a non-importable design reference; no live code imports helm_domain.
  - Night Runner is treated as deprecated tooling with scripts left runnable but all prompts/runbooks quarantined under docs/archive.
  - EmailAgent remains wired for storage/runtime and replay, but is explicitly non-truth; StudyAgent is frozen with no new usage added.
  - Worker replay for failed email triage runs is wired through build_email_agent_runtime so tests can mock the runtime cleanly.
patterns_established:
  - Use a maintained classification inventory plus rg sweeps as the diagnostic surface for deprecated/quarantined integrations.
  - Quarantine deprecated packages and docs under docs/archive/ instead of leaving them importable or truth-defining.
  - Keep Email/Study runtime/storage contracts intact while constraining their truth status via docs, inventory, and tests.
observability_surfaces:
  - uv run --frozen --extra dev pytest -q tests/unit tests/integration
  - rg "night runner|night-runner" .
  - rg "linkedin" .
  - rg "helm_domain" .
  - .gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md
  - bash scripts/test.sh
  - .github/workflows/python-checks-reusable.yml
drill_down_paths:
  - .gsd/milestones/M002/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S02/tasks/T03-SUMMARY.md
duration: ~3h
verification_result: passed
completed_at: 2026-03-13T21:56:00-07:00
---

# S02: Repo cleanup and deprecation enforcement

**Quarantined or updated deprecated/aspirational surfaces (Night Runner, packages/domain, Email/Study) in line with the M002 truth set, and confirmed tests/CI and diagnostics now focus on the workflow-engine core.**

## What Happened

- Consumed the M002 truth note, classification rules, and refined classification inventory from S01 to ground cleanup decisions in the workflow-engine truth set (task/calendar, status, replay, operator surfaces).
- T01 mapped real usage of deprecated and aspirational surfaces (Night Runner, packages/domain, EmailAgent/StudyAgent) via rg sweeps and static inspection, then rewrote the classification inventory to per-file/module granularity with explicit keep/freeze/deprecate/quarantine statuses and coupling notes.
- T02 applied that inventory to the tree:
  - Confirmed there is no concrete LinkedIn connector code; LinkedIn remains a logical deprecate/remove entry only.
  - Quarantined the aspirational domain package by moving packages/domain under docs/archive/packages-domain and removing packages/domain/src from all runtime PYTHONPATH helpers.
  - Quarantined Night Runner runbooks/prompts under docs/archive/, updating scripts/night-runner.sh and docs to point at the archived prompt while keeping the scripts runnable as deprecated tooling.
  - Updated docs/internal/helm-v1.md to treat the domain package and Night Runner workstream as historical design references, not live implementation contracts.
  - Updated the classification inventory to reflect new archive paths and quarantined statuses for domain and Night Runner assets.
- T03 trimmed Email/Study to non-truth runtime/storage surfaces while keeping wiring intact:
  - Confirmed EmailAgent is deprecated (runtime/storage/worker wiring kept) and StudyAgent is frozen per truth note and inventory.
  - Ensured Email/Study docs and tests remain present but are not expanded; no new truth-defining docs were added.
  - Fixed worker replay wiring by having apps/worker/src/helm_worker/jobs/replay.py import build_email_agent_runtime from helm_runtime.email_agent and pass it into run_replay_queue, matching test expectations and making email replay runtime injectable.
  - Audited scripts/test.sh and .github/workflows/python-checks-reusable.yml to confirm CI runs the same pytest entrypoint without treating Email/Study as special or truth-defining.
- Verified the combined changes via tests, rg sweeps, and static checks, ensuring Night Runner and domain-layer code no longer shape the live import graph while Email/Study remain constrained to non-truth roles.

## Verification

- Tests:
  - uv run --frozen --extra dev pytest -q tests/unit tests/integration
    - Covers workflow kernel, task/calendar specialists, approval, sync, replay, and Email/Study wiring.
    - Initially surfaced a gap in replay worker wiring; after wiring build_email_agent_runtime into replay.py, the full unit and integration suite passed.
  - bash scripts/test.sh
    - Delegates to the same uv/pytest command and is green after the replay wiring fix.
- Static checks:
  - python -m compileall .
    - python is not on PATH in this environment; earlier T02 work used python3 -m compileall . successfully to validate imports across the tree, including archived domain code. The slice relies on that prior static check and the now-passing pytest run for coverage.
- Deprecated surface scans:
  - rg "linkedin" .
    - No matches; LinkedIn remains logical-only in the classification docs.
  - rg "night runner" . / rg "Night Runner" .
    - Matches confined to scripts/night-runner.sh, scripts/install-night-runner-cron.sh, docs/archive/night-runner.md, docs/archive/night-runner-prompt.md, and historical references in docs/internal/helm-v1.md that explicitly mark the workstream as deprecated and point to archive paths.
  - rg "helm_domain" .
    - No matches; after quarantining packages/domain, there are no remaining imports or references in live code, tests, or scripts.
  - rg "EmailAgent|StudyAgent" .
    - Matches limited to expected runtime/config/storage surfaces, worker jobs, tests, and docs listed in the classification inventory.
- Inventory alignment:
  - .gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md now contains entries for each Night Runner, domain, and Email/Study artifact surfaced by rg, with explicit statuses and rationales; no unclassified matches remain.

## Requirements Advanced

- R002 — Repo working set is reduced to active and frozen truth: Deprecated Night Runner and domain-layer artifacts are quarantined under docs/archive/, LinkedIn remains logical-only, and tests/CI now run without relying on these aspirational paths.
- R004 — Non-core agents do not define current truth: EmailAgent and StudyAgent remain present, but truth-defining behavior is constrained to task/calendar flows; EmailAgent is explicitly deprecated, StudyAgent is frozen, and Email/Study tests/docs are treated as non-truth in inventory and wiring.
- R005 — Deprecated paths are clearly marked and removed where safe: LinkedIn, Night Runner, and packages/domain are explicitly classified and either physically quarantined or confirmed absent from live code, with diagnostics (rg + inventory) documenting their status.

## Requirements Validated

- R002 — Repo working set is reduced to active and frozen truth: Passing test suite, absence of helm_domain imports, and confinement of Night Runner to scripts + archived docs demonstrate that non-truth surfaces no longer shape runtime behavior.
- R005 — Deprecated paths are clearly marked and removed where safe: The combination of quarantined archive locations, updated docs, and rg-based diagnostics provides durable proof that deprecated paths are clearly marked and not treated as live options.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- LinkedIn cleanup is purely logical: the plan anticipated concrete connector code, but S02 confirmed there is no LinkedIn implementation in the tree. The slice therefore only ensures there are no stray references and maintains LinkedIn as a deprecate/remove entry in the inventory.
- Night Runner scripts remain runnable: instead of full removal, scripts/night-runner.sh and scripts/install-night-runner-cron.sh are left in scripts/ but explicitly classified as deprecated and pointed at archived docs; this matches the truth-set bias toward quarantine when removal might hide useful historical tooling.
- Static compile check uses python3: in T02, python3 -m compileall . was used successfully; in this environment python is not on PATH, so S02 relies on the earlier python3 compile run plus the now-passing pytest run for static coverage.

## Known Limitations

- Night Runner scripts still exist as deprecated tooling; they are not exercised by the primary test suite. Future milestones may choose to remove them entirely once they are no longer useful as a historical reference.
- EmailAgent retains a relatively large surface area (storage/runtime/worker/jobs/tests) compared to its non-truth status. The slice constrains its influence but does not aggressively shrink the surface.
- StudyAgent remains frozen with existing surfaces intact; no additional guardrails are added beyond classification and absence of new usage.

## Follow-ups

- Consider a future cleanup pass to either remove Night Runner scripts entirely or move them under an explicit legacy/ directory once they are no longer needed as examples.
- Narrow the EmailAgent runtime interface and consider quarantining higher-level email planning flows under a legacy/ namespace while keeping storage schemas and minimal runtime helpers.
- When S03 completes end-to-end task/calendar UAT, revisit docs/internal/helm-v1.md to ensure email/study sections match the final truth-set framing and do not overstate Email/Study capabilities.

## Files Created/Modified

- `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` — Refined to per-file/module classification with explicit statuses for Night Runner, packages/domain, EmailAgent/StudyAgent surfaces, and logical LinkedIn entries; updated to reflect archive moves.
- `docs/internal/helm-v1.md` — Marked domain-layer and Night Runner sections as historical/deprecated, pointing to docs/archive/ and clarifying that storage models, not the domain package, define current truth.
- `docs/archive/night-runner.md` — Quarantined Night Runner runbook; updated references to point at docs/archive/night-runner-prompt.md and deprecated scripts.
- `docs/archive/night-runner-prompt.md` — Quarantined Night Runner prompt used by scripts/night-runner.sh.
- `docs/archive/packages-domain/` — New location for the aspirational domain package, removed from importable namespaces but preserved as a design reference.
- `apps/worker/src/helm_worker/jobs/replay.py` — Wired replay jobs through build_email_agent_runtime so email triage replays have a concrete runtime and tests can mock it cleanly.
- `scripts/night-runner.sh` — Updated to reference archived Night Runner prompt; remains runnable as deprecated tooling.
- `scripts/install-night-runner-cron.sh` — Continues to manage Night Runner cron entries but is now anchored to archived docs; classified as deprecated.
- `scripts/new-migration.sh`, `scripts/run-worker.sh`, `scripts/run-telegram-bot.sh`, `scripts/migrate.sh`, `scripts/run-api.sh` — Removed packages/domain/src from PYTHONPATH to keep the quarantined domain layer out of live runtime paths.
- `scripts/test.sh` — Confirmed as the primary test entrypoint (uv run --frozen --extra dev pytest); no Email/Study-specific wiring added.
- `.github/workflows/python-checks-reusable.yml` — Confirmed to delegate to scripts/test.sh and scripts/lint.sh without treating Email/Study as truth-defining.
- `.gsd/milestones/M002/slices/S02/tasks/T01-SUMMARY.md`, `.gsd/milestones/M002/slices/S02/tasks/T02-SUMMARY.md`, `.gsd/milestones/M002/slices/S02/tasks/T03-SUMMARY.md` — Task-level records feeding this slice summary.

## Forward Intelligence

### What the next slice should know

- The classification inventory is now the authoritative map for deprecated/quarantined surfaces; any new references to LinkedIn, Night Runner, helm_domain, or expanded Email/Study behavior should be added there and justified.
- All domain-layer code has been moved under docs/archive/packages-domain and is no longer importable via helper scripts; task/calendar workflows rely solely on storage models and orchestration code.
- EmailAgent replay wiring is now explicit in apps/worker/src/helm_worker/jobs/replay.py via build_email_agent_runtime; tests rely on this for monkeypatching and isolation.

### What's fragile

- EmailAgent’s large surface area relative to its non-truth status means future changes around replay or storage could accidentally elevate its importance; keep changes minimal and always check the classification inventory and truth note before expanding behavior.
- Night Runner scripts are deprecated but still runnable; if they silently break (e.g., due to environment changes), it will not affect core workflows but may confuse anyone trying to use them as tooling.

### Authoritative diagnostics

- uv run --frozen --extra dev pytest -q tests/unit tests/integration — primary proof surface for workflow kernel, task/calendar, replay, and Email/Study wiring after cleanup.
- .gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md — single source of truth for what is active/frozen/deprecated/quarantined.
- rg "night runner|night-runner" ., rg "linkedin" ., rg "helm_domain" . — quick checks that deprecated surfaces remain confined to archive/docs and classification inventory.

### What assumptions changed

- Assumed there was a concrete LinkedIn connector to remove; in reality, LinkedIn exists only as a planned integration and classification entry.
- Assumed packages/domain might still be partially wired into runtime; in practice, it was safe to quarantine entirely and remove all PYTHONPATH references without breaking tests.
- Assumed replay jobs were fully wired for EmailAgent; tests revealed a runtime_factory gap that S02 corrected by explicitly wiring build_email_agent_runtime.
