---
status: complete
phase: 04-representative-scheduling-workflow
source:
  - 04-01-SUMMARY.md
  - 04-02-SUMMARY.md
started: 2026-03-13T03:20:00Z
updated: 2026-03-13T03:32:00Z
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
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""
