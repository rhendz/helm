---
estimated_steps: 10
estimated_files: 2
---

# T03: Integration into Workflow Commands

**Slice:** S03 — Telegram Real-Time Execution UX
**Milestone:** M003

## Description

Wire the sync formatters and query methods into the existing Telegram workflow commands. Extend `/workflows` to show sync timelines, add `/workflow_sync_detail` for deep-dive inspection, and verify backward compatibility.

## Steps

1. Read existing `_format_run()` function in `workflows.py` to understand current output structure and patterns
2. Modify `_format_run()` to include sync timeline:
   - Check if run has sync records by calling `list_sync_events()` on the service
   - If sync records exist, fetch sync details and format timeline via `sync_events.format_sync_timeline()`
   - Append formatted timeline to output lines (after completion summary, before next actions)
   - Keep the change transparent: if no sync records, timeline is empty string (no clutter)
   - Preserve all existing output (status line, completion summary, next actions)
3. Create new async command handler `async def sync_detail(update, context)`:
   - Follow existing pattern from `recent()` and `detail()` handlers
   - Use `parse_single_id_arg(context.args, command_name="workflow_sync_detail")` to extract run_id
   - Call `_service.get_sync_details(run_id)` to fetch full sync data
   - Format timeline via `sync_events.format_sync_timeline()` with max_events=None (show all)
   - Handle errors gracefully: if run not found, reply "Run not found"; if no sync records, reply "No sync events for this run"
   - Reply with formatted message
4. Register the new command handler in bot's command list (wherever other `/workflow_*` commands are registered)
5. Update command help text or documentation to mention new `/workflow_sync_detail <run_id>` command
6. Create integration test file `tests/integration/test_telegram_workflow_sync_commands.py`
7. Write integration tests:
   - Test `/workflows <run_id>` with real run and sync records: verify sync timeline is included
   - Test `/workflow_sync_detail <run_id>` with real run: verify full timeline is returned
   - Test error handling: invalid run_id, non-existent run, run with no sync records
   - Test backward compatibility: existing `/workflows` without args still works, existing `/workflows <run_id>` still shows completion summary
   - Test command parsing: verify `parse_single_id_arg()` handles edge cases (missing arg, non-numeric arg)
8. Verify all existing workflow command tests still pass (no regressions)
9. Run full test suite to confirm integration
10. Manual verification: In a running bot environment, test both commands with real Telegram client; verify messages are readable, formatting is correct, no command errors

## Must-Haves

- [ ] `/workflows <run_id>` extended to show sync timeline after completion summary
- [ ] `/workflow_sync_detail <run_id>` command added and working
- [ ] Backward compatibility verified: existing `/workflows` commands unchanged
- [ ] Error handling robust (missing run, no sync records, invalid args)
- [ ] Integration tests covering happy path, edge cases, error handling
- [ ] All existing tests still pass (zero regressions)

## Verification

- `pytest tests/integration/test_telegram_workflow_sync_commands.py -v` — All command tests pass
- `pytest tests/unit/test_workflow_telegram_commands.py -v` — Existing formatter tests still pass
- `pytest tests/ -v` — Full test suite passes with no regressions
- Manual Telegram client verification: Both commands execute correctly and produce readable output

## Observability Impact

- Signals added: Structured log when `/workflows` and `/workflow_sync_detail` commands are invoked (run_id, user_id, sync record count returned)
- How a future agent inspects: Grep logs for "workflow_command_invoked" to see command history; check return counts to understand sync data availability
- Failure state exposed: Command errors (run not found, parsing errors) logged with context; Telegram replies clearly indicate the problem

## Inputs

- T01 output: `TelegramWorkflowStatusService.list_sync_events()` and `get_sync_details()`
- T02 output: `sync_events.format_sync_record()`, `format_drift_event()`, `format_sync_timeline()`
- Existing `workflows.py` — command handler patterns, `parse_single_id_arg()`, error handling
- S02 summary — confirms sync records and drift events are available in the database

## Expected Output

- Modified `workflows.py` with extended `_format_run()` and new `sync_detail()` command handler
- New file `tests/integration/test_telegram_workflow_sync_commands.py` with 5+ passing integration tests
- All command handlers integrated into bot's dispatcher
- Documentation/help text updated to mention new command
- Zero regressions in existing tests; full test suite green
