---
status: diagnosed
phase: 04-representative-scheduling-workflow
source:
  - 04-01-SUMMARY.md
  - 04-02-SUMMARY.md
started: 2026-03-13T03:20:00Z
updated: 2026-03-13T03:40:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

[testing complete]

## Tests

### 1. Start Weekly Scheduling Run
expected: Starting the representative workflow from Telegram-style input or the API creates a `weekly_scheduling` run from the shared request contract. The run should preserve the raw weekly brief, parse task/constraint metadata durably, and show the representative workflow rather than the old weekly digest path.
result: pass

### 2. Review Proposal At Approval Checkpoint
expected: After the run processes the request, the proposal view should show scheduled blocks, honored constraints, assumptions, carry-forward work, and downstream change preview, while pausing for approval before any task or calendar writes happen.
result: pass

### 3. Request A Revision
expected: Requesting a revision with natural-language feedback should create a new proposal version for the same run, keep the prior version in history, and return the workflow to an approval-ready state with the revised proposal visible.
result: pass

### 4. Approve And Inspect Completed Run
expected: Approving the representative proposal should execute the approved task and calendar writes, complete the run, and show an outcome-first completion summary with scheduled results, sync status, carry-forward items, and inspectable final-summary lineage.
result: pass

### 5. Inspect Recovery Or Replay State
expected: If the workflow enters a recovery-oriented state such as replay requested, the shared API and Telegram summaries should describe downstream follow-up truthfully rather than collapsing the run into a generic queued or completed message.
result: issue
reported: "/workflow_replay 1 Check replay recovery summary. left /workflows showing the run as an ordinary completed run with no recovery-oriented summary."
severity: major

## Summary

total: 5
passed: 4
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "If the workflow enters a recovery-oriented state such as replay requested, the shared API and Telegram summaries should describe downstream follow-up truthfully rather than collapsing the run into a generic queued or completed message."
  status: failed
  reason: "User reported: /workflow_replay 1 Check replay recovery summary. left /workflows showing the run as an ordinary completed run with no recovery-oriented summary."
  severity: major
  test: 5
  root_cause: "The shared workflow status projection prioritizes stale successful final-summary state over live replay-requested recovery state, so completed-then-replayed runs still render as ordinary completed runs."
  artifacts:
    - path: "apps/api/src/helm_api/services/workflow_status_service.py"
      issue: "Completion headline and summary logic prefer persisted final-summary success over live sync recovery classification."
    - path: "packages/orchestration/src/helm_orchestration/workflow_service.py"
      issue: "Final summary is created at sync completion and not refreshed when replay later changes downstream follow-up state."
    - path: "tests/unit/test_replay_service.py"
      issue: "Missing completed-then-replay coverage for representative runs."
    - path: "tests/unit/test_workflow_status_service.py"
      issue: "Missing shared projection coverage for completed representative runs that later become replay-requested."
    - path: "tests/unit/test_telegram_commands.py"
      issue: "Missing `/workflows` replay-summary coverage for completed representative runs."
  missing:
    - "Make live replay/recovery classification override stale completed-success messaging in shared completion summaries."
    - "Project downstream sync status and attention items from live sync recovery state when replay is active."
    - "Add representative tests for completed -> replay-requested summaries in API/status and Telegram `/workflows` output."
  debug_session: ".planning/debug/phase-04-replay-recovery-summary-gap.md"
