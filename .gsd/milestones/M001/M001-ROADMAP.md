# M001: Helm Orchestration Kernel v1

**Vision:** Helm Orchestration Kernel is the durable workflow engine for Helm, a personal internal AI system. It ships a reusable kernel that can run multi-step workflows with typed specialist dispatch, durable artifacts, approval-gated side effects, restart-safe resume, replay-aware recovery, and shared operator surfaces across API and Telegram.

## Success Criteria

- Durable workflow runs, steps, artifacts, and lineage are persisted and inspectable.
- Typed specialist dispatch with durable invocation records.
- Approval checkpoints with revision-driven proposal versioning and kernel-owned resume semantics.
- Adapter-gated sync execution with idempotency, retry, replay, and recovery classification.
- Representative weekly scheduling workflow from request through approved writes and replay-aware final lineage.

## Slices

- [x] **S01: Durable Workflow Foundation** `risk:medium` `depends:[]`
  > After this: Establish the durable Postgres persistence layer for workflow runs, step attempts, artifacts, and transition history.
- [x] **S02: Specialist Dispatch And Approval Semantics** `risk:medium` `depends:[S01]`
  > After this: Implement kernel-owned specialist dispatch for `TaskAgent` and `CalendarAgent`, including durable invocation records and schedule proposal persistence.
- [x] **S03: Adapter Writes And Recovery Guarantees** `risk:medium` `depends:[S02]`
  > After this: Establish the durable sync-plan and adapter contract layer for approved workflow writes.
- [x] **S04: Representative Scheduling Workflow** `risk:medium` `depends:[S03]`
  > After this: Implement the real representative weekly scheduling workflow on top of the existing kernel primitives.
