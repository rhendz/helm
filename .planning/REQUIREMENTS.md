# Requirements: Helm Orchestration Kernel v1

**Defined:** 2026-03-11
**Core Value:** Helm can execute multi-step, approval-gated workflows reliably enough that workflow state, artifacts, and side effects remain durable and inspectable across restarts and failures.

## v1 Requirements

### Workflow Lifecycle

- [x] **FLOW-01**: User can start a workflow run from a new request and Helm persists the run with a unique ID, current status, and current step.
- [x] **FLOW-02**: User can inspect the current status of a workflow run, including active step, paused state, and final outcome.
- [x] **FLOW-03**: Helm persists step transitions so an in-flight workflow can resume from the correct step after a restart.
- [x] **FLOW-04**: Helm persists failure details for a failed workflow run, including failed step, error summary, and retryability state.

### Specialist Dispatch

- [x] **AGNT-01**: Helm can invoke `TaskAgent` with typed input derived from raw workflow input.
- [x] **AGNT-02**: Helm can invoke `CalendarAgent` with typed scheduling input derived from validated task artifacts and calendar constraints.
- [x] **AGNT-03**: Helm persists an invocation record for each specialist execution, including input reference, output reference, timing, and result status.
- [x] **AGNT-04**: Helm validates specialist outputs before any downstream workflow step or adapter write consumes them.
- [x] **AGNT-05**: Helm marks a workflow step as validation-failed when a specialist output is malformed, incomplete, or ambiguous enough to violate the step schema.
- [x] **AGNT-06**: Helm persists validation-failure details and prevents downstream execution until the workflow is explicitly retried, revised, or terminated.

### Artifacts

- [x] **ARTF-01**: Helm persists the raw user input that created a workflow run.
- [x] **ARTF-02**: Helm persists structured task artifacts produced from the user request, including task priority, estimated duration, deadlines, and dependencies when available.
- [x] **ARTF-03**: Helm persists validation results, including warnings and ambiguity flags, for intermediate workflow artifacts.
- [x] **ARTF-04**: Helm persists schedule proposal artifacts produced by `CalendarAgent`, including proposed time blocks and proposed calendar changes.
- [x] **ARTF-05**: Helm persists a final workflow summary artifact that links the request, specialist outputs, approval decisions, and downstream sync results.

### Approval And Resume

- [x] **APRV-01**: Helm pauses a workflow before any downstream create, update, or delete side effect against a task system or calendar system.
- [x] **APRV-02**: User can approve, reject, or request revision for a pending approval checkpoint.
- [x] **APRV-03**: Helm persists the approval request, the allowed actions, the final decision, and the decision timestamp.
- [x] **APRV-04**: Helm resumes a paused workflow from the correct step after an approval, rejection, or revision decision.
- [x] **APRV-05**: Helm persists revised proposals as new artifact versions rather than overwriting prior proposal artifacts.
- [x] **APRV-06**: User can inspect which proposal version was approved, rejected, or superseded by a revision.

### Adapters And Sync

- [x] **SYNC-01**: Helm writes approved task updates through a task-system adapter rather than directly from workflow logic.
- [x] **SYNC-02**: Helm writes approved calendar updates through a calendar adapter rather than directly from workflow logic.
- [x] **SYNC-03**: Helm persists adapter sync records for each outbound write, including target system, attempt status, and external object ID when created or updated.
- [x] **SYNC-04**: Helm prevents duplicate downstream writes when a workflow step is retried after failure.
- [x] **SYNC-05**: Helm prevents duplicate downstream writes when a paused or interrupted workflow is resumed after restart or operator action.
- [x] **SYNC-06**: Helm uses persisted idempotency data or equivalent sync keys so downstream create, update, and delete actions can be reconciled safely across retry and resume paths.

### Recovery And Replay

- [x] **RCVR-01**: Helm can recover an in-flight workflow after worker or process restart without losing run lineage.
- [x] **RCVR-02**: Helm can retry a failed workflow step by re-attempting the same step within the same workflow run while preserving prior artifacts, failure records, and idempotency protections.
- [x] **RCVR-03**: Helm can replay a workflow step or run as an intentional re-execution event with explicit lineage to the original failed or prior execution.
- [x] **RCVR-04**: Helm records enough workflow state to distinguish recoverable failures from terminal failures.

### Representative Workflow

- [x] **DEMO-01**: User can submit a weekly scheduling request containing multiple tasks and Helm creates a workflow run for that request.
- [x] **DEMO-02**: Helm converts the weekly scheduling request into normalized task artifacts through `TaskAgent`.
- [x] **DEMO-03**: Helm converts normalized tasks into a schedule proposal through `CalendarAgent`.
- [x] **DEMO-04**: Helm pauses for approval before any downstream create, update, or delete of tasks or calendar blocks.
- [x] **DEMO-05**: Helm can create a revised scheduling proposal as a new version after user feedback at the approval checkpoint.
- [x] **DEMO-06**: Helm completes the representative scheduling workflow with full lineage from raw request to downstream sync results.

## v2 Requirements

### Additional Specialists

- **AGNT-07**: Helm can register and invoke additional specialist agents through the same typed kernel contract.
- **AGNT-08**: Helm can support generalized dynamic routing across more than two specialist agents after the fixed representative workflows have proven the common kernel contract.

### Operator Experience

- [x] **OPER-01**: User can inspect and control workflow runs through richer Telegram and API tooling, including artifact browsing and step-level replay options.
- **OPER-02**: User can compare revisions of a proposal before approving a later attempt.

### Workflow Breadth

- **FLOW-05**: Helm can run additional domain workflows such as email or study flows on the same kernel contract.
- **FLOW-06**: Helm can coordinate multiple workflow templates with shared artifact and adapter infrastructure.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Expanding email-specific product workflows | Kernel infrastructure is the current priority, not domain breadth |
| Expanding study-specific product workflows | Kernel comes first so later study flows inherit the durable contract |
| New primary dashboard or web UI | Telegram-first remains the V1 operator experience |
| Unsupervised outbound writes | V1 requires explicit approval before meaningful external actions |
| Multi-tenant workflow platform features | Helm remains a single-user internal system in V1 |
| Large catalog of specialist agents | V1 should validate the kernel with `TaskAgent` and `CalendarAgent` first |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FLOW-01 | Phase 1 | Complete |
| FLOW-02 | Phase 1 | Complete |
| FLOW-03 | Phase 1 | Complete |
| FLOW-04 | Phase 1 | Complete |
| AGNT-01 | Phase 2 | Complete |
| AGNT-02 | Phase 2 | Complete |
| AGNT-03 | Phase 2 | Complete |
| AGNT-04 | Phase 1 | Complete |
| AGNT-05 | Phase 1 | Complete |
| AGNT-06 | Phase 1 | Complete |
| ARTF-01 | Phase 1 | Complete |
| ARTF-02 | Phase 1 | Complete |
| ARTF-03 | Phase 1 | Complete |
| ARTF-04 | Phase 2 | Complete |
| ARTF-05 | Phase 1 | Complete |
| APRV-01 | Phase 2 | Complete |
| APRV-02 | Phase 2 | Complete |
| APRV-03 | Phase 2 | Complete |
| APRV-04 | Phase 2 | Complete |
| APRV-05 | Phase 2 | Complete |
| APRV-06 | Phase 2 | Complete |
| SYNC-01 | Phase 3 | Complete |
| SYNC-02 | Phase 3 | Complete |
| SYNC-03 | Phase 3 | Complete |
| SYNC-04 | Phase 3 | Complete |
| SYNC-05 | Phase 3 | Complete |
| SYNC-06 | Phase 3 | Complete |
| RCVR-01 | Phase 3 | Complete |
| RCVR-02 | Phase 3 | Complete |
| RCVR-03 | Phase 3 | Complete |
| RCVR-04 | Phase 3 | Complete |
| OPER-01 | Phase 3 | Complete |
| DEMO-01 | Phase 4 | Complete |
| DEMO-02 | Phase 2 | Complete |
| DEMO-03 | Phase 2 | Complete |
| DEMO-04 | Phase 4 | Complete |
| DEMO-05 | Phase 4 | Complete |
| DEMO-06 | Phase 4 | Complete |

**Coverage:**
- v1 requirements: 36 total
- Mapped to phases: 36
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-11*
*Last updated: 2026-03-12 after completing Phase 3 plan 05*
