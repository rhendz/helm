---
phase: 03-adapter-writes-and-recovery-guarantees
plan: 05
subsystem: api
tags: [fastapi, telegram, worker, replay, recovery, postgres]
requires:
  - phase: 03-04
    provides: shared workflow status projection with sync recovery semantics
provides:
  - Explicit workflow replay API route with typed request and response contracts
  - Shared replay service handoff used by API, worker, and Telegram entrypoints
  - Telegram replay command and replay-aware workflow action rendering
affects: [api, worker, telegram, recovery, replay]
tech-stack:
  added: []
  patterns:
    - Shared replay service mediates operator replay across app entrypoints
    - Telegram action rendering merges operator actions and safe recovery actions from status projections
key-files:
  created: [tests/unit/test_replay_service.py]
  modified:
    - apps/api/src/helm_api/routers/replay.py
    - apps/api/src/helm_api/schemas.py
    - apps/api/src/helm_api/services/replay_service.py
    - apps/worker/src/helm_worker/jobs/replay.py
    - apps/telegram-bot/src/helm_telegram_bot/main.py
    - apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py
    - apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py
    - tests/unit/test_workflow_status_service.py
    - tests/unit/test_telegram_commands.py
key-decisions:
  - "Explicit replay requests are validated against safe_next_actions from the shared workflow status projection before orchestration enqueues new sync lineage."
  - "Worker replay jobs delegate workflow replay execution to the shared replay service so queue consumption does not invent replay policy."
  - "Telegram surfaces replay by merging safe recovery actions with existing operator actions and exposing replay as a distinct command from retry."
patterns-established:
  - "Replay entrypoints stay thin: they translate operator intent into WorkflowOrchestrationService.request_sync_replay rather than re-deriving sync policy."
  - "Telegram workflow summaries should surface safe_next_actions when recovery actions differ from available_actions."
requirements-completed: [RCVR-04, OPER-01]
duration: 24min
completed: 2026-03-12
---

# Phase 03 Plan 05: Replay Entry Points Summary

**Explicit workflow replay now ships through typed FastAPI routes, shared worker handoff, and Telegram recovery commands without collapsing replay into retry semantics**

## Performance

- **Duration:** 24 min
- **Started:** 2026-03-12T23:00:00Z
- **Completed:** 2026-03-12T23:24:46Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- Added a typed `/v1/replay/workflow-runs/{run_id}` API route that only accepts explicit replay when the shared workflow status projection marks replay as the safe operator action.
- Routed workflow replay queue items through a shared replay execution entrypoint so the worker only handles queue consumption and observability.
- Added Telegram replay support via `/workflow_replay` and replay-aware workflow summaries that surface `safe_next_actions` distinctly from retry.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add registered API replay entrypoints on top of the kernel replay model** - `1de013f` (feat)
2. **Task 2: Wire worker replay execution without duplicating app-layer policy** - `4e87f9b` (feat)
3. **Task 3: Surface replay and recovery actions in Telegram using the shared status projection** - `cf09913` (feat)

## Files Created/Modified

- `tests/unit/test_replay_service.py` - Covers API replay acceptance and rejection plus worker replay queue handoff.
- `apps/api/src/helm_api/services/replay_service.py` - Validates explicit workflow replay requests and exposes shared workflow replay execution helpers.
- `apps/api/src/helm_api/routers/replay.py` - Registers the workflow replay API route with typed request and response models.
- `apps/api/src/helm_api/schemas.py` - Adds workflow replay request and response schema contracts.
- `apps/worker/src/helm_worker/jobs/replay.py` - Delegates workflow replay queue items to the shared replay service.
- `apps/telegram-bot/src/helm_telegram_bot/commands/workflows.py` - Merges safe replay actions into workflow summaries and adds `/workflow_replay`.
- `apps/telegram-bot/src/helm_telegram_bot/services/workflow_status_service.py` - Routes Telegram replay requests through the shared replay service.
- `apps/telegram-bot/src/helm_telegram_bot/main.py` - Registers the replay command in the shipped Telegram bot entrypoint.
- `tests/unit/test_telegram_commands.py` - Verifies replay-aware workflow summaries and the explicit replay command path.
- `tests/unit/test_workflow_status_service.py` - Verifies Telegram replay wrapper usage and bot command registration.

## Decisions Made

- Replay requests now gate on `safe_next_actions` so API and Telegram surfaces cannot request replay when retry remains the correct recovery path.
- Worker replay execution uses the shared replay service rather than embedding workflow replay branching in the worker job.
- Telegram workflow summaries now render both `available_actions` and `safe_next_actions` so replay and await-replay states stay visible to operators.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added replay command and command tests outside the listed plan file set**
- **Found during:** Task 3
- **Issue:** The planned verification file covered Telegram service wiring and registration, but the changed bot command surface still needed direct command behavior coverage.
- **Fix:** Updated `tests/unit/test_telegram_commands.py` with replay-specific command and summary assertions.
- **Files modified:** tests/unit/test_telegram_commands.py
- **Verification:** `uv run --frozen --extra dev pytest tests/unit/test_telegram_commands.py -k workflow`
- **Committed in:** cf09913

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Added test coverage only. No scope creep in runtime code.

## Issues Encountered

- Parallel `git add` calls contended on `.git/index.lock`; staging reverted to sequential git operations for task commits.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Replay is reachable from shipped API and Telegram entrypoints and can be consumed by the worker queue.
- Recovery surfaces now share a single replay request path, so future work can extend replay execution semantics without changing operator-facing entrypoints again.

## Self-Check

PASSED
