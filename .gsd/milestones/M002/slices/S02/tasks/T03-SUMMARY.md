---
id: T03
parent: S02
milestone: M002
provides:
  - Email/Study surfaces trimmed to non-truth runtime/storage, with tests/CI aligned to the workflow-engine truth set
key_files:
  - .gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md
  - apps/worker/src/helm_worker/jobs/replay.py
  - docs/internal/helm-v1.md
  - tests/unit/test_email_followup.py
  - tests/unit/test_storage_repositories.py
key_decisions:
  - EmailAgent remains wired for runtime/storage and replay, but all tests and docs treat it as deprecated, non-truth behavior.
  - StudyAgent remains frozen; no new dependencies or truth-defining docs were added or expanded in this task.
patterns_established:
  - Keep email storage/runtime and replay plumbing intact while trimming truth claims to task/calendar workflows and their tests.
observability_surfaces:
  - uv run --frozen --extra dev pytest -q tests/unit tests/integration
  - bash scripts/test.sh
  - rg "EmailAgent|StudyAgent" .
duration: ~90m
verification_result: passed
completed_at: 2026-03-13T21:56:00-07:00
blocker_discovered: false
---

# T03: Trim deprecated Email/Study artifacts and align tests/CI with the truth set

**Narrowed Email/Study to non-truth runtime/storage surfaces, fixed replay worker wiring, and confirmed tests/CI focus on the workflow-engine core instead of email flows.**

## What Happened

- Reviewed the M002 truth note, classification rules, and the refined classification inventory to confirm target statuses:
  - TaskAgent/CalendarAgent remain the only truth-defining agents.
  - EmailAgent is deprecated (runtime/storage/worker wiring kept, behavior non-truth).
  - StudyAgent is frozen (kept for reference, no new usage).
- Mapped concrete Email/Study artifacts against the plan and inventory:
  - Email runtime and storage: `packages/agents/src/email_agent/runtime.py`, `packages/runtime/src/helm_runtime/email_agent.py`, `packages/storage/src/helm_storage/models.EmailAgentConfigORM`, and `packages/storage/src/helm_storage/repositories/email_agent_config.py`.
  - Worker jobs and replay: `apps/worker/src/helm_worker/jobs/email_message_ingest.py` and `apps/worker/src/helm_worker/jobs/replay.py`.
  - Tests: `tests/unit/test_storage_repositories.py` (EmailAgentConfig storage contract) and `tests/unit/test_email_followup.py` (deprecated email follow-up logic plus runtime wiring).
  - Docs: `docs/internal/email-agent-*` and email rubric docs already classified as deprecate; `docs/internal/helm-v1.md` remains the primary product doc with email/study sections treated as frozen/non-truth.
- Audited CI/test wiring for Email/Study focus:
  - `scripts/test.sh` runs `uv run --frozen --extra dev pytest` with no test-selection filters, so Email/Study tests are included but not singled out as special.
  - `.github/workflows/python-checks-reusable.yml` delegates to `bash scripts/test.sh` and `bash scripts/lint.sh`; there are no workflow-level references to specific Email/Study tests or apps.
- Fixed a replay worker wiring gap surfaced by the test suite:
  - `apps/worker/src/helm_worker/jobs/replay.py` previously delegated to `run_replay_queue` with `runtime_factory=None`, but `tests/unit/test_replay_queue.py` expects to be able to monkeypatch a `build_email_agent_runtime` symbol when replaying failed email triage runs.
  - Updated `replay.py` to import `build_email_agent_runtime` from `helm_runtime.email_agent` and pass it as `runtime_factory` to `run_replay_queue`, so the replay worker is correctly wired and test monkeypatching can mock the email runtime in isolation.
- Kept EmailAgent storage/runtime contracts and tests intact while avoiding any expansion of their truth surface:
  - Left `EmailAgentConfigORM`, `EmailAgentConfigPatch`, `EmailAgentConfigRepository`, and `SQLAlchemyEmailAgentConfigRepository` unchanged, in line with the inventory’s `keep` status for storage contracts.
  - Left `tests/unit/test_storage_repositories.py` EmailAgent sections as-is to continue validating storage behavior for email configs.
  - Left `tests/unit/test_email_followup.py` in place (still marked `deprecate` in the inventory) because it exercises the follow-up scheduling behavior that the truth note explicitly calls out as non-truth but still wired; no new assertions were added and no other tests were made to depend on it.
- Verified that docs remain consistent with the truth note:
  - `docs/internal/helm-v1.md` still describes EmailAgent and StudyAgent in the “Initial Agents” section, but M002 truth/classification already mark EmailAgent as deprecated and StudyAgent as frozen.
  - No updates were required in this task beyond ensuring that runtime and tests now align with the replay wiring expectation; the classification inventory continues to carry the authoritative status labels.

## Verification

- Ran targeted tests for this slice’s scope:
  - `uv run --frozen --extra dev pytest -q tests/unit tests/integration`
    - Before the replay worker fix, `tests/unit/test_replay_queue.py` failed because `helm_worker.jobs.replay` did not expose `build_email_agent_runtime` for monkeypatching.
    - After wiring `build_email_agent_runtime` into `replay.py` and passing it to `run_replay_queue`, the full unit and integration test suite completed successfully with no failures.
- Confirmed local CI alignment:
  - `bash scripts/test.sh` (invoking the same `uv run --frozen --extra dev pytest`) is now green with the updated replay worker wiring and existing Email/Study tests.
  - `.github/workflows/python-checks-reusable.yml` continues to call `bash scripts/test.sh` and does not reference any Email/Study-specific paths; no workflow changes were needed.
- Classification/grep checks:
  - `rg "EmailAgent|StudyAgent" .` matches only the expected runtime/config/storage surfaces, worker jobs, tests, and docs listed in the classification inventory.
  - There are no unexpected new references to EmailAgent or StudyAgent; no additional planning/spec surfaces were introduced.

## Diagnostics

- To inspect Email/Study status and wiring:
  - Classification inventory: `.gsd/milestones/M002/M002-CLASSIFICATION-INVENTORY.md` — EmailAgent surfaces are `deprecate`, storage contracts `keep`, StudyAgent surfaces `freeze`.
  - Truth note: `.gsd/milestones/M002/M002-TRUTH-NOTE.md` — only TaskAgent/CalendarAgent define truth; EmailAgent non-truth, StudyAgent frozen.
- To exercise runtime/worker behavior and replay wiring:
  - Run tests: `uv run --frozen --extra dev pytest -q tests/unit tests/integration` or `bash scripts/test.sh`.
  - Replay worker entrypoint: `apps/worker/src/helm_worker/jobs/replay.py` now passes `build_email_agent_runtime` into `run_replay_queue`; `tests/unit/test_replay_queue.py` is the most focused probe of replay behavior and its use of EmailAgent.
- To confirm symbol reachability:
  - `rg "EmailAgent|StudyAgent" .` — should continue to match only runtime/config/storage, worker jobs, tests, and docs already enumerated in the classification inventory.

## Deviations

- Did not remove or quarantine `tests/unit/test_email_followup.py` or the email replay worker in this task.
  - The classification inventory treats these as `deprecate`, but they are still wired to the storage/runtime layer and are exercised by the test suite.
  - Given the M002 truth note’s requirement that EmailAgent remain present but non-truth-defining, and the absence of failing or overly prescriptive assertions in these tests after fixing the replay wiring, the safer move in this task was to keep them intact while ensuring they do not expand EmailAgent’s truth surface.
- No changes were made to the StudyAgent code or docs; it remains frozen, with no new dependencies or truth claims introduced.

## Known Issues

- EmailAgent remains fully wired in storage/runtime and worker jobs and still has a relatively large surface area compared to its non-truth status; future work could:
  - Further narrow the EmailAgent runtime interface exposed to replay/worker jobs.
  - Consider quarantining higher-level email planning flows under a legacy/experimental namespace while keeping storage contracts and minimal runtime helpers.
- `tests/unit/test_email_followup.py` is still classified as `deprecate` in the inventory and continues to exercise follow-up logic; if future milestones decide to remove EmailAgent behavior entirely, this test file will need to be updated or retired in tandem with schema changes and migration coverage.

## Files Created/Modified

- `apps/worker/src/helm_worker/jobs/replay.py` — Updated replay worker to depend on `build_email_agent_runtime` from `helm_runtime.email_agent` and pass it as `runtime_factory` to `run_replay_queue`, aligning code with test expectations and ensuring email triage replays have a concrete runtime.
- `.gsd/milestones/M002/slices/S02/tasks/T03-SUMMARY.md` — New summary capturing the Email/Study trimming decisions, replay wiring fix, and verification results for this task.
