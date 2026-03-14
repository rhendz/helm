---
id: T03
parent: S03
milestone: M002
provides:
  - Hardened unit tests for Telegram workflow commands around completion and replay semantics
  - Explicit test coverage for weekly scheduling completion summaries and safe_next_actions
  - Verification that Telegram formatting remains aligned with workflow status projections
key_files:
  - tests/unit/test_workflow_telegram_commands.py
  - .gsd/milestones/M002/slices/S03/tasks/T03-PLAN.md
key_decisions: []
patterns_established:
  - Unit test pattern for Telegram command formatting using mock service objects and monkeypatch
observability_surfaces:
  - Unit test assertions that fail when completion_summary fields (headline, sync counts, approval decisions) diverge from expected values
  - Test failures surface if safe_next_actions or approval_checkpoint formatting changes unexpectedly
duration: 45 minutes
verification_result: passed
completed_at: 2026-03-13
blocker_discovered: false
---

# T03: Harden Telegram workflow commands around completion and replay

**Added 7 new unit tests to explicitly protect Telegram completion/replay semantics for weekly scheduling workflows.**

## What Happened

Reviewed the existing Telegram workflow command implementations (`apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py`) and discovered the implementation already correctly surfaces:
- **completion_summary** fields: headline, sync counts (total, task, calendar), scheduled_highlights, carry_forward_tasks
- **approval_checkpoint** messaging: artifact ID, version, proposal_summary, available actions
- **safe_next_actions**: actions pulled from both `available_actions` and `safe_next_actions` via `_next_actions()` helper

The code was well-aligned with API projections and the UAT script, but test coverage was thin. Added comprehensive unit tests to lock in this behavior and catch regressions early.

### Tests Added

1. **`test_workflow_completion_summary_surfaces_sync_counts`** — Verifies Telegram formats completion summary with:
   - Outcome headline from completion_summary
   - Sync write counts (total, task, calendar) with status
   - Scheduled item highlights
   - Carry-forward tasks

2. **`test_workflow_completion_summary_absent_when_not_completed`** — Confirms completion summary is NOT shown for active runs (only surfaces on completed runs)

3. **`test_workflow_approval_checkpoint_shows_artifact_and_proposal`** — Validates approval checkpoint displays:
   - Target artifact ID and version
   - Proposal summary
   - Explicit instruction to name artifact ID in approval commands

4. **`test_workflow_safe_next_actions_on_completed_run_with_replay_option`** — Ensures `safe_next_actions` (e.g., replay) appear in "Next:" field for completed runs

5. **`test_workflow_lists_needs_action_shows_approval_checkpoint`** — Confirms runs needing action display approval checkpoints via `/workflow_needs_action`

6. **`test_workflow_reject_parses_ids_and_calls_service`** — Verifies `/reject` command surfaces run state after rejection

7. **`test_workflow_request_revision_parses_ids_feedback_and_calls_service`** — Verifies `/request_revision` command parses feedback and surfaces run state

### Key Assertions

All tests use semantic assertions that protect core semantics without over-specifying formatting:
- Presence of key phrases ("Outcome:", "Sync:", "Carry forward:", etc.)
- Correct count values from completion_summary
- Approval checkpoint fields (artifact ID, version, proposal)
- Safe next actions in "Next:" output

Tests fail immediately if:
- Completion_summary fields are missing from API response
- Telegram formatting drops sync counts or approval decision info
- Safe_next_actions extraction breaks
- Approval checkpoint display is removed or mangled

## Verification

✅ All 11 tests in `tests/unit/test_workflow_telegram_commands.py` pass:
```bash
uv run --frozen --extra dev pytest -q tests/unit/test_workflow_telegram_commands.py
```
Result: 11 passed

✅ All existing tests in `tests/unit/test_telegram_commands.py` still pass (93 tests) — no regressions.

✅ Integration tests still pass (3 tests in `test_weekly_scheduling_end_to_end.py`).

✅ Telegram command implementations require zero changes — existing code already correctly formats completion summaries, approval checkpoints, and safe_next_actions.

### Test Behavior Under Regression

Demonstrated that tests catch regressions:
- Removing sync write counts from completion_summary → Test fails with assertion on "Sync:" line
- Dropping approval_checkpoint display → Test fails when artifact ID not found in output
- Missing safe_next_actions extraction → Test fails when replay action not in "Next:" field

## Diagnostics

To inspect what these tests protect:

1. **Check completion_summary formatting**:
   ```bash
   # Read the completion_summary structure from workflow_status_service
   grep -n "completion_summary\|total_sync_writes\|task_sync_writes" \
     apps/api/src/helm_api/services/workflow_status_service.py | head -20
   ```

2. **Verify Telegram formatting logic**:
   ```bash
   # See _format_run() function that surfaces completion_summary
   grep -n "_format_run\|completion_summary\|Sync:" \
     apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py
   ```

3. **Run a test with verbose output to see assertions**:
   ```bash
   uv run --frozen --extra dev pytest -vv tests/unit/test_workflow_telegram_commands.py::test_workflow_completion_summary_surfaces_sync_counts
   ```

4. **Cross-check UAT expectations**:
   ```bash
   # The completion summary in the UAT script phase 4.3 matches test expectations
   grep -A10 "completion_summary\|Sync:" .gsd/milestones/M002/slices/S03/uat.md
   ```

## Deviations

No deviations from the task plan. The task called for adding tests to cover completion and replay semantics. Telegram command implementations already aligned with API projections, so no code changes were needed.

## Known Issues

None. Tests pass, and Telegram command behavior is now explicitly protected by unit tests that will catch regressions when projections change.

## Files Created/Modified

- `tests/unit/test_workflow_telegram_commands.py` — Added 7 new test functions (previous 4 existing tests now 11 total)
- `.gsd/milestones/M002/slices/S03/tasks/T03-PLAN.md` — Added Observability Impact section during pre-flight (required by system)

## Integration with Slice

With T01 (UAT script) and T02 (integration tests) complete, T03 provides the final verification layer:
- **T01** — Documents expected operator-facing behavior in a walkthrough script
- **T02** — Validates the API and worker semantics with automated integration tests
- **T03** — Protects Telegram command formatting through unit tests, ensuring operator surface consistency

Together, these three tasks fulfill the slice goal: prove weekly scheduling works end-to-end via API, worker, and Telegram, with explicit test coverage and an operator runbook.

## Next: Slice Verification

The slice plan's verification checks can now be executed:
```bash
# Test verification (should all pass)
uv run --frozen --extra dev pytest -q \
  tests/integration/test_weekly_scheduling_end_to_end.py \
  tests/unit/test_workflow_telegram_commands.py

# UAT execution (manual, from fresh environment with Postgres)
bash scripts/run-api.sh & bash scripts/run-worker.sh & bash scripts/run-telegram-bot.sh
# Then follow ./.gsd/milestones/M002/slices/S03/uat.md
```

All tasks in S03 are now complete. Ready for slice-level verification and closure.
