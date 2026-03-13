# Roadmap: Helm Orchestration Kernel v1

## Overview

This roadmap turns the current Helm codebase into a reusable orchestration kernel without expanding product-domain scope. The sequence is deliberate: first establish durable workflow state and artifact boundaries, then add specialist dispatch and approval semantics, then make downstream writes and recovery safe, and finally prove the kernel with a fixed end-to-end scheduling workflow that exercises the full lifecycle.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Durable Workflow Foundation** - Establish the kernel's durable run, step, artifact, and validation model.
- [ ] **Phase 2: Specialist Dispatch And Approval Semantics** - Add typed specialist invocation plus first-class approval, revision, and resume behavior.
- [ ] **Phase 3: Adapter Writes And Recovery Guarantees** - Make downstream side effects safe, idempotent, and recoverable across retry and resume.
- [ ] **Phase 4: Representative Scheduling Workflow** - Prove the kernel with the fixed weekly task-to-calendar workflow from request through approved side effects.

## Phase Details

### Phase 1: Durable Workflow Foundation
**Goal**: Helm has a durable workflow run model with persisted step state, artifacts, validation results, and inspectable run status.
**Depends on**: Nothing (first phase)
**Requirements**: FLOW-01, FLOW-02, FLOW-03, FLOW-04, ARTF-01, ARTF-02, ARTF-03, ARTF-05, AGNT-04, AGNT-05, AGNT-06
**Success Criteria** (what must be TRUE):
  1. User can create a workflow run and inspect its current step and status through existing operator surfaces.
  2. Workflow state and artifacts survive process restart and can resume from the persisted step boundary.
  3. Validation failures are stored as durable step outcomes and block downstream execution cleanly.
  4. Every run has inspectable lineage linking raw input, step transitions, artifacts, and final state.
**Plans**: 3 plans

Plans:
- [x] 01-01: Add workflow run, step state, and artifact persistence models plus repositories.
- [ ] 01-02: Add typed workflow schemas, validation boundaries, and validation-failure handling.
- [ ] 01-03: Expose run status and artifact inspection through API and Telegram-friendly read paths.

### Phase 2: Specialist Dispatch And Approval Semantics
**Goal**: Helm can execute typed `TaskAgent` and `CalendarAgent` steps, create approval checkpoints, support revision versioning, and resume from decisions safely.
**Depends on**: Phase 1
**Requirements**: AGNT-01, AGNT-02, AGNT-03, ARTF-04, APRV-01, APRV-02, APRV-03, APRV-04, APRV-05, APRV-06, DEMO-02, DEMO-03
**Success Criteria** (what must be TRUE):
  1. Helm invokes `TaskAgent` and `CalendarAgent` through a shared typed kernel contract with invocation records.
  2. Helm pauses before downstream create, update, or delete actions and records an approval request as durable workflow state.
  3. User can approve, reject, or request revision, and the workflow resumes from the correct step.
  4. Revised proposals are stored as new artifact versions with inspectable decision lineage.
**Plans**: 3 plans

Plans:
- [ ] 02-01: Implement specialist step execution contracts and invocation recording inside the orchestration kernel.
- [ ] 02-02: Implement approval request storage, decision handling, and pause/resume transitions.
- [ ] 02-03: Add proposal revision/versioning flow for approval-driven rework.

### Phase 3: Adapter Writes And Recovery Guarantees
**Goal**: Approved workflows can write through adapters safely with strong idempotency, retry, replay, and sync lineage guarantees.
**Depends on**: Phase 2
**Requirements**: SYNC-01, SYNC-02, SYNC-03, SYNC-04, SYNC-05, SYNC-06, RCVR-01, RCVR-02, RCVR-03, RCVR-04
**Success Criteria** (what must be TRUE):
  1. Task and calendar side effects execute only through adapter boundaries after approval.
  2. Retry and resume paths do not create duplicate downstream objects or lose sync lineage.
  3. Replay is recorded as an explicit lineage event rather than being confused with retry.
  4. Failed runs clearly distinguish recoverable failures from terminal failures and expose the next safe operator action.
**Plans**: 3 plans

Plans:
- [ ] 03-01: Implement task-system and calendar adapter contracts with sync-record persistence.
- [ ] 03-02: Add idempotency keys, duplicate-write prevention, and reconciliation behavior across retry and resume.
- [ ] 03-03: Add retry vs replay semantics, recovery state tracking, and operator-safe failure handling.

### Phase 4: Representative Scheduling Workflow
**Goal**: Helm proves the kernel with the weekly scheduling workflow from raw user request through approved downstream writes.
**Depends on**: Phase 3
**Requirements**: DEMO-01, DEMO-04, DEMO-05, DEMO-06
**Success Criteria** (what must be TRUE):
  1. User can submit a weekly task-planning request and Helm creates a representative workflow run end to end.
  2. The workflow produces normalized task artifacts, scheduling proposals, approval checkpoints, and approved adapter writes using the shared kernel.
  3. Revision feedback at the approval gate produces a new proposal version without losing lineage to earlier attempts.
  4. The completed run exposes full lineage from raw input to external sync results and final summary.
**Plans**: 2 plans

Plans:
- [ ] 04-01: Implement the fixed weekly scheduling workflow on top of the kernel primitives.
- [ ] 04-02: Add end-to-end verification, restart/recovery checks, and operator-facing completion summaries for the representative flow.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Durable Workflow Foundation | 1/3 | In Progress | - |
| 2. Specialist Dispatch And Approval Semantics | 0/3 | Not started | - |
| 3. Adapter Writes And Recovery Guarantees | 0/3 | Not started | - |
| 4. Representative Scheduling Workflow | 0/2 | Not started | - |
