---
status: passed
phase: 04-representative-scheduling-workflow
source:
  - 04-01-SUMMARY.md
  - 04-02-SUMMARY.md
started: 2026-03-13T03:20:00Z
updated: 2026-03-13T23:55:00Z
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
result: pass
reported: "Live Telegram verification on March 13, 2026 showed `/workflow_replay 3 Check replay recovery summary.` leaving `/workflows` in a replay-aware state with `Next: await_replay`, recovery-oriented outcome text, and `status=replay_requested`."

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0

## Gaps

- none
