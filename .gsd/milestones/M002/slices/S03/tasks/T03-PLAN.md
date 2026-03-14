---
estimated_steps: 6
estimated_files: 3
---

# T03: Harden Telegram workflow commands around completion and replay

**Slice:** S03 — Task/calendar workflow protection and verification
**Milestone:** M002

## Description

Strengthen Telegram workflow command coverage so that completion and replay behavior for weekly scheduling runs is explicitly protected by tests and remains aligned with the shared workflow status projection. This task focuses on ensuring Telegram presents accurate completion summaries and replay options for task/calendar workflows, without over-specifying string formats, and that changes to projections or replay semantics surface as test failures rather than silent regressions.

## Steps

1. Review `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py` and `apps/telegram-bot/src/helm_telegram_bot/services/command_service.py` to understand how Telegram formats workflow lists, completion summaries, and replay-related commands for weekly scheduling runs.
2. Inspect existing unit tests in `tests/unit/test_workflow_telegram_commands.py` and `tests/unit/test_telegram_commands.py` to see what aspects of completion and replay are currently asserted.
3. Identify gaps where weekly scheduling completion summaries or replay semantics are not explicitly covered (e.g., missing assertions on task/calendar counts, recovery/replay cues, or safe_next_actions exposure).
4. Add or refine unit tests to cover these gaps, asserting on core semantics (presence of key phrases/counts, replay options) while avoiding brittle full-string equality where minor formatting changes are acceptable.
5. If necessary, make minimal adjustments to Telegram command formatting to better surface existing completion summary and replay information from `workflow_status_service` while keeping behavior consistent with the UAT script.
6. Run the relevant unit tests (`tests/unit/test_workflow_telegram_commands.py` and related files) until they pass and clearly fail when Telegram output diverges from expected weekly scheduling semantics.

## Must-Haves

- [ ] Telegram tests explicitly cover weekly scheduling completion summaries and replay messaging, including safe_next_actions where applicable.
- [ ] Telegram command behavior for weekly scheduling remains consistent with the shared workflow status projection and the UAT script, without over-specifying incidental formatting.

## Verification

- `uv run --frozen --extra dev pytest -q tests/unit/test_workflow_telegram_commands.py tests/unit/test_telegram_commands.py`
- Manually compare Telegram output expectations in tests against the flow described in `./.gsd/milestones/M002/slices/S03/uat.md` to ensure alignment.

## Inputs

- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py`, `apps/telegram-bot/src/helm_telegram_bot/services/command_service.py` — current Telegram workflow command implementations.
- `tests/unit/test_workflow_telegram_commands.py`, `tests/unit/test_telegram_commands.py` — existing tests to extend.
- `apps/api/src/helm_api/services/workflow_status_service.py` — source of completion/replay semantics used by Telegram.

## Expected Output

- Strengthened tests in `tests/unit/test_workflow_telegram_commands.py` (and possibly `tests/unit/test_telegram_commands.py`) that assert on Telegram completion/replay semantics for weekly scheduling.
- Any minimal, necessary updates in `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py` to keep Telegram behavior aligned with the status projection and UAT script.

## Observability Impact

**What signals change:**
- New unit test assertions explicitly surface expected Telegram output for weekly scheduling completion summaries, replay options, and safe_next_actions presence.
- Test failures will immediately catch if Telegram formatting diverges from expected completion semantics (e.g., missing task/calendar counts, missing replay cues, changed status labels).
- Telegram command code changes (if any) will be visible in git diff and test expectations; the UAT script workflow output comparison validates alignment.

**How a future agent inspects this:**
1. Run `uv run --frozen --extra dev pytest -q tests/unit/test_workflow_telegram_commands.py tests/unit/test_telegram_commands.py` to check Telegram command test coverage.
2. Review test assertions in the modified test files to understand what Telegram output is expected for weekly scheduling (completion summaries, replay options, counts).
3. Compare test expectations against `apps/api/src/helm_api/services/workflow_status_service.py` to verify alignment with the shared workflow status projection.
4. Execute the UAT script (`./.gsd/milestones/M002/slices/S03/uat.md`) manually to visually confirm Telegram outputs match test expectations and the UAT narrative.
5. Inspect git log for this task to see minimal changes made to `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py` (if any).

**What failure state becomes visible:**
- Test failures in `test_workflow_telegram_commands.py` or `test_telegram_commands.py` indicate Telegram output has diverged from expected weekly scheduling semantics (missing counts, changed completion phrases, absent replay options).
- UAT script execution shows mismatches between expected Telegram completion summaries and what the bot actually returns (missing information, unexpected formatting).
- Regression detection: if future changes to `workflow_status_service` projections or Telegram command formatting are made without updating tests, those changes will fail the test suite immediately, preventing silent regressions.