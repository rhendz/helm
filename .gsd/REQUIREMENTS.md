# Requirements

## Validated

- **REQ-DURABLE-PERSISTENCE**: Durable workflow runs, steps, artifacts, and lineage are persisted and inspectable — validated in M001 (S01 established 4 core tables with typed repositories and hermetic test coverage)
- **REQ-SPECIALIST-DISPATCH**: Typed TaskAgent and CalendarAgent dispatch with durable invocation records — validated in M001 (S02/T01 added specialist invocation table with input/output artifact linkage)
- **REQ-APPROVAL-CHECKPOINTS**: Approval checkpoints, revision-driven proposal versioning, and kernel-owned resume semantics — validated in M001 (S02/T02-T03 added checkpoint table with version-targeted decisions)
- **REQ-ADAPTER-SYNC**: Adapter-gated sync execution with idempotency, retry, replay, and recovery classification — validated in M001 (S03 added sync records with adapter protocols, replay lineage, recovery classification)
- **REQ-REPRESENTATIVE-WORKFLOW**: Representative weekly scheduling workflow from request through approved writes and replay-aware final lineage — validated in M001 (S04 wired end-to-end flow with shared request contract)
- **REQ-OPERATOR-SURFACES**: Telegram and API operator tooling for workflow status, approval, replay, and lineage inspection — validated in M001 (shared status projection consumed by API routes and Telegram commands)

## Active

- **REQ-REVISION-COMPARE**: Compare proposal revisions before approving a later attempt
- **REQ-ADDITIONAL-SPECIALISTS**: Register and invoke additional specialist agents through the same typed kernel contract
- **REQ-ADDITIONAL-WORKFLOWS**: Run additional domain workflows, such as email or study flows, on the same kernel contract
- **REQ-WORKFLOW-COORDINATION**: Coordinate multiple workflow templates with shared artifact and adapter infrastructure

## Out of Scope

- New primary dashboard or web UI while Telegram remains the primary operator surface
- Unsupervised outbound writes that bypass explicit approval
- Multi-tenant or public-product abstractions
- Broad workflow expansion before the next milestone explicitly defines scope
