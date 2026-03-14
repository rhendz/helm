# S03: Adapter Writes And Recovery Guarantees

**Established the durable sync-plan and adapter contract layer for approved workflow writes with idempotency, retry, replay, recovery classification, and shared operator projections.**

## What Happened

S03 was the largest slice (5 tasks) and built the complete outbound write infrastructure. T01 added the `workflow_sync_records` table, adapter protocols, and orchestration logic to expand approved proposals into deterministic sync manifests. T02 implemented idempotent adapter execution with reconciliation-first recovery, durable outcome states, and restart-safe worker resume. T03 added explicit recovery classification (recoverable, terminal, retry, replay, terminate-after-partial-success), replay lineage generations, and termination snapshots. T04 projected all sync and recovery facts through the shared workflow status service so operator surfaces read durable sync counts, recovery class, and replay lineage directly. T05 wired explicit replay entry points through typed API routes, shared worker handoff, and Telegram commands.

## Key Outcomes

- Durable `workflow_sync_records` with identity anchored to proposal, version, target, kind, and planned item key.
- Task and calendar adapter protocols with normalized request/outcome/reconciliation envelopes.
- Orchestration-owned execution order, failure classification, and reconciliation policy.
- Replay creates new sync lineage generations preserving prior history.
- Termination cancels remaining sync and records partial counts.
- Shared status projection reads sync counts, recovery class, and replay lineage from durable facts.
- Explicit replay routes in API, worker, and Telegram distinct from retry.

## Verification

- `test_workflow_repositories.py`: sync record durability, lineage, remaining/failed queries, recovery metadata, termination snapshots.
- `test_workflow_orchestration_service.py`: deterministic ordering, retryable stop, reconciliation-first resume, restart-safe retry, replay vs retry lineage, terminal failure, terminate-after-partial-success.
- `test_workflow_status_service.py`: effect summaries, sync counts, recovery summaries, replay-after-termination lineage.
- `test_replay_service.py`: API replay acceptance/rejection, worker replay handoff.
- `test_telegram_commands.py`: replay-aware workflow summaries and explicit replay command.

## Tasks

- T01 (20 min): Sync-record schema, adapter contracts, approved sync manifest preparation.
- T02 (17 min): Idempotent adapter execution, reconciliation-first recovery, restart-safe resume.
- T03 (10 min): Recovery classification, replay lineage generations, terminate-after-partial-success.
- T04 (9 min): Shared status projection for effect summaries and recovery state.
- T05 (24 min): Replay entry points via API, worker, and Telegram.
