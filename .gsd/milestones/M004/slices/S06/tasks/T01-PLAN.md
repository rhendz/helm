---
estimated_steps: 8
estimated_files: 10
---

# T01: Merge milestone/M004 into main and verify full test suite

**Slice:** S06 — Dev experience, observability, and cleanup
**Milestone:** M004

## Description

Merge the `milestone/M004` branch (containing S01–S04 implementation: LLM inference, `/task` handler, `/status` command, approval policy, proactive notifications, scheduling primitives refactor) into `main` (which has S05 test infrastructure + calendar_id threading). This is the critical path for M004 — without it, nothing is deployable.

The merge has real conflicts that must be resolved with specific rules (documented below). The verification gate is the full test suite passing at 440+ tests with 0 failures.

**Relevant skills:** None needed — this is a git merge with conflict resolution.

## Steps

1. **Inspect current branch state.** You are on `main`. Run `git log --oneline -5` to confirm. Run `git log --oneline milestone/M004 -5` to confirm the milestone branch tip. Both branches share a common ancestor.

2. **Start the merge.** Run `git merge milestone/M004 --no-commit` to stage the merge without auto-committing. This gives you control over conflict resolution. If git reports conflicts, note which files.

3. **Resolve `packages/orchestration/src/helm_orchestration/schemas.py`.** This is the most critical conflict. The rules:
   - `main` added `calendar_id: str = "primary"` to `SyncLookupRequest` (S05) — **KEEP this field**.
   - `milestone/M004` added `urgency: str | None = None` and `confidence: float | None = None` to `WeeklyTaskRequest` — **KEEP these fields**.
   - `milestone/M004` added the `TaskSemantics` model — **KEEP the model** (it should already be present on `main` from the S05/T04 port).
   - The merged file must have ALL three additions. Read the file after resolution to verify all three are present.

4. **Resolve `packages/orchestration/src/helm_orchestration/__init__.py`.** Both branches export the same symbols but in different order. The conflict is just `__all__` ordering. Merge all symbols into `__all__` — ensure `TaskSemantics`, `ApprovalPolicy`, `ConditionalApprovalPolicy`, `compute_reference_week`, `parse_local_slot`, `past_event_guard`, `PastEventError`, `to_utc`, `ApprovalDecision`, `ApprovalDecisionResult` are all present. Sort alphabetically within the list for consistency.

5. **Resolve `packages/connectors/src/helm_connectors/google_calendar.py`.** `main` has `calendar_id` threading (reads from payload/request, no hardcoded `"primary"`). `milestone/M004` still has `calendarId="primary"` hardcoded. **Take `main`'s version** — it has the correct staging-safe pattern. If the merge auto-resolved this wrong, manually verify:
   - `upsert_calendar_block` reads `calendar_id = payload.get("calendar_id") or "primary"` — NOT hardcoded.
   - `reconcile_calendar_block` uses `request.calendar_id` — NOT hardcoded `"primary"`.
   - Structlog entries include `calendar_id=calendar_id` field.

6. **Resolve `apps/worker/src/helm_worker/jobs/workflow_runs.py`.** Take `milestone/M004`'s refactored version (uses `compute_reference_week`, `parse_local_slot`, `to_utc`, `past_event_guard`, removes `_candidate_slots` legacy code). BUT fix these specific lines:
   - Find ALL `calendar_id="primary"` hardcodes in the milestone version (at lines ~219 and ~414 in milestone). Replace with `calendar_id=os.getenv("HELM_CALENDAR_TEST_ID", "primary")` (same pattern `main` uses).
   - Verify `_RANGE_PATTERN` is kept (used by `_parse_duration_from_title`).
   - Verify `_DAY_OFFSETS`, `_TIME_PATTERN`, `_parse_slot_from_title` are NOT present (milestone already removed these).
   - Verify the hardcoded `datetime(2026, 3, 16, 9, tzinfo=UTC)` is NOT present (milestone replaced with `compute_reference_week`).

7. **Resolve `tests/e2e/conftest.py`.** **Take `main`'s version** — it has the safety gates (`pytest_configure` fail-fast, `pytest_collection_modifyitems` skip-all, `e2e_calendar_id` fixture). `milestone/M004` removed these. Read the file after resolution and verify `pytest_configure`, `pytest_collection_modifyitems`, and `e2e_calendar_id` are all present.

8. **Resolve remaining conflicts:**
   - `tests/unit/test_workflow_telegram_commands.py` → Take `milestone/M004` version (has `execute_after_approval_called` assertions and 2-reply check).
   - `tests/integration/test_google_calendar_adapter_real_api.py` — if there's a conflict because `main` moved this to `tests/unit/test_google_calendar_adapter.py`, delete from `tests/integration/` (keep `main`'s move).
   - `tests/conftest.py` — ensure this exists post-merge (from milestone; sets `OPERATOR_TIMEZONE=America/Los_Angeles`).
   - `.gsd/` files — take `main`'s versions for `STATE.md` and `PROJECT.md`.
   - `.env.example`, `.gitignore`, `contracts.py`, `config.py`, `client.py`, `digest_delivery.py`, `approve.py` — these should merge cleanly; verify no conflicts.
   - New files from milestone that have no conflict: `commands/task.py`, `commands/status.py`, `test_scheduling_primitives.py`, `test_task_command.py`, `test_task_inference.py`, `test_task_execution.py`, `test_status_command.py` — these should auto-add.

9. **Run the full test suite.** Execute: `uv run --frozen pytest tests/unit/ tests/integration/ --ignore=tests/integration/test_study_agent_mvp.py --ignore=tests/unit/test_study_agent_mvp.py -q`. Target: 440+ passed, 0 failures. The study_agent_mvp test is a pre-existing unrelated failure — ignore it.

10. **Commit the merge.** `git add -A && git commit -m "chore(S06/T01): Merge milestone/M004 (S01-S04) into main"`. Do NOT use `--no-verify` — let pre-commit hooks run.

## Must-Haves

- [ ] `SyncLookupRequest.calendar_id` field is present in merged `schemas.py`
- [ ] `TaskSemantics` model is present in merged `schemas.py`
- [ ] `WeeklyTaskRequest.urgency` and `WeeklyTaskRequest.confidence` fields are present
- [ ] `google_calendar.py` reads `calendar_id` from payload/request (no hardcoded `"primary"`)
- [ ] `workflow_runs.py` uses `os.getenv("HELM_CALENDAR_TEST_ID", "primary")` for `calendar_id` (not hardcoded)
- [ ] `workflow_runs.py` uses `compute_reference_week` (no hardcoded `datetime(2026, 3, 16, ...)`)
- [ ] `tests/e2e/conftest.py` has safety gates (`pytest_configure`, `pytest_collection_modifyitems`, `e2e_calendar_id`)
- [ ] `tests/conftest.py` sets `OPERATOR_TIMEZONE=America/Los_Angeles`
- [ ] `tests/unit/test_workflow_telegram_commands.py` has `execute_after_approval` assertions
- [ ] 440+ tests pass with 0 failures (excluding study_agent_mvp)

## Verification

- `uv run --frozen pytest tests/unit/ tests/integration/ --ignore=tests/integration/test_study_agent_mvp.py --ignore=tests/unit/test_study_agent_mvp.py -q` → 440+ passed, 0 failures
- `grep "calendar_id" packages/orchestration/src/helm_orchestration/schemas.py | grep SyncLookup` → shows the field
- `grep "calendar_id" packages/connectors/src/helm_connectors/google_calendar.py | head -5` → shows dynamic reading
- `grep "HELM_CALENDAR_TEST_ID" apps/worker/src/helm_worker/jobs/workflow_runs.py` → shows env var override
- `grep "pytest_configure\|e2e_calendar_id" tests/e2e/conftest.py` → shows safety gates
- `test -f tests/conftest.py && echo OK` → exists

## Inputs

- `milestone/M004` branch — S01–S04 implementation (LLM inference, `/task` handler, `/status` command, approval policy, proactive notifications, scheduling refactor)
- `main` branch — S05 test infrastructure (E2E safety gates, calendar_id threading, SyncLookupRequest.calendar_id, misclassified test moved)
- Research doc conflict resolution rules (inlined in Steps above)

## Expected Output

- Unified `main` branch with all S01–S05 code
- 440+ tests passing, 0 failures
- Clean merge commit on `main`
