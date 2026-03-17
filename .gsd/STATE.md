# GSD State

**Active Milestone:** M004 — Foundation Repair
**Active Slice:** None (planning complete, ready for S01)
**Active Task:** None
**Phase:** Ready to execute

## Milestone Registry
- ✅ **M001:** Helm Orchestration Kernel v1
- ✅ **M002:** Helm Truth-Set Cleanup
- ✅ **M003:** Task/Calendar Productionization
- 🔄 **M004:** Foundation Repair — planning complete

## Recent Decisions
- D001: Keep custom DB-backed step runner for M004 (issues are implementation quality, not architecture)
- D002: `/task` storage as workflow artifact for M004; dedicated tasks table deferred to M005
- D003: Immediate execution inline from Telegram handler; polling as background recovery only
- D004: Shared scheduling primitives in `packages/orchestration/src/helm_orchestration/scheduling.py`
- D005: `OPERATOR_TIMEZONE` env var, required, fail-fast, IANA format, visible in `/status`

## Blockers
- None

## Next Action
Begin S01: Task inference engine and `/task` quick-add.

Key files to read before starting:
- `.gsd/milestones/M004/M004-CONTEXT.md` — implementation decisions, risks, codebase references
- `.gsd/milestones/M004/M004-ROADMAP.md` — slice plan and boundary map
- `apps/worker/src/helm_worker/jobs/workflow_runs.py` — stub task agent to replace
- `packages/llm/src/helm_llm/client.py` — LLMClient to extend with inference
- `packages/orchestration/src/helm_orchestration/schemas.py` — schemas to extend
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py` — existing `/workflow_start` handler pattern

S01 delivers: `infer_task_semantics()`, `/task` command handler, `TaskSemantics` schema, `ConditionalApprovalPolicy` interface stub, `WeeklyTaskRequest` extended with urgency/confidence fields.
