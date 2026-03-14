# T03: 04-representative-scheduling-workflow 03

**Slice:** S04 — **Milestone:** M001

## Description

Close the diagnosed Phase 4 replay-summary gap without replanning the representative workflow.

Purpose: Make completed-then-replayed representative runs render truthfully as replay-requested recovery work by fixing shared status precedence and adding the minimum regression coverage around replay, status projection, and Telegram summaries.
Output: One focused projection fix in the shared status service plus targeted tests that prove stale final-summary success no longer masks live replay recovery state.

## Must-Haves

- [ ] "A representative run that later becomes replay-requested must project the live recovery state even when a successful final-summary artifact still exists from the prior completed execution."
- [ ] "Shared status precedence must come from durable live recovery signals before stale outcome messaging so API and Telegram operator surfaces stay truthful."
- [ ] "Replay-requested summaries must preserve inspectable completion lineage while clearly signaling that downstream follow-up is now pending operator attention."
- [ ] "The fix must stay in the shared projection path rather than adding Telegram-only branching or mutating previously persisted completion artifacts."

## Files

- `apps/api/src/helm_api/services/workflow_status_service.py`
- `tests/unit/test_replay_service.py`
- `tests/unit/test_workflow_status_service.py`
- `tests/unit/test_telegram_commands.py`
