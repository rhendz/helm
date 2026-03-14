# Pitfalls Research

**Domain:** Durable orchestration kernel for a personal AI workflow system
**Researched:** 2026-03-11
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Fake Durability

**What goes wrong:**
The workflow appears restart-safe in demos but actually loses step context, approval state, or side-effect lineage after a crash or deploy.

**Why it happens:**
Teams persist final artifacts but not intermediate step state, pending approvals, or retry metadata.

**How to avoid:**
Persist run state, step state, invocation records, approvals, artifacts, and sync records as first-class entities.

**Warning signs:**
Restart tests require manual repair, approval requests cannot be resumed deterministically, or operators rely on logs to reconstruct state.

**Phase to address:**
Phase 1: workflow lifecycle and persistence foundation

---

### Pitfall 2: Duplicate External Writes on Retry

**What goes wrong:**
Calendar blocks or downstream tasks are created twice when a worker restarts or a run is retried.

**Why it happens:**
Side effects are performed inline without idempotency keys or persisted sync history.

**How to avoid:**
Execute side effects through adapters that record attempt IDs, idempotency keys, external object IDs, and final outcomes.

**Warning signs:**
Retries re-run the same outbound call blindly or replay depends on "just don't click twice."

**Phase to address:**
Phase 3: adapter execution and approval-gated writes

---

### Pitfall 3: Kernel Logic Stays Trapped in Domain Agents

**What goes wrong:**
Each new workflow copies lifecycle logic, validation, pause/resume handling, and error policy from the last one.

**Why it happens:**
It feels faster to extend the currently working domain package than to extract a real orchestration boundary.

**How to avoid:**
Move run lifecycle, step contracts, approvals, and replay semantics into `packages/orchestration`, leaving specialists focused on their bounded job.

**Warning signs:**
Workflow state transitions live inside `email_agent`-style modules or app services instead of reusable orchestration code.

**Phase to address:**
Phase 2: orchestration boundary extraction

---

### Pitfall 4: Approval Is Only a UI Concept

**What goes wrong:**
The bot shows an approval prompt, but the underlying workflow has no persisted paused state or resumable decision record.

**Why it happens:**
Approval is implemented as a message flow instead of a kernel state transition.

**How to avoid:**
Model approvals as durable records tied to run ID, step ID, requested actions, allowed decisions, and resolution timestamps.

**Warning signs:**
Approvals disappear after restart, or the system cannot answer "what exactly was approved?"

**Phase to address:**
Phase 2: approval and resume semantics

---

### Pitfall 5: Agent Output Bleeds Into Adapters Unchecked

**What goes wrong:**
Raw model text or loosely shaped dicts drive scheduling and writes directly, causing brittle behavior and unsafe side effects.

**Why it happens:**
Schema discipline feels slower during early iteration.

**How to avoid:**
Require typed artifacts, explicit validation, and ambiguity flags before any downstream step or adapter executes.

**Warning signs:**
Adapters accept free-form payloads, or operator revisions require manually editing JSON in logs.

**Phase to address:**
Phase 1: typed workflow artifacts and validation

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Reusing domain-specific tables for kernel state | Fast initial progress | Blurs ownership and makes future workflows harder to generalize | Acceptable only if wrapped by kernel repositories and migrated later |
| Storing approval context only in Telegram messages | Easy to ship | No durable lineage or safe restart recovery | Never acceptable for the kernel |
| Using ad hoc dict payloads between steps | Low friction | Validation drift and replay brittleness | Acceptable only in prototypes before schemas are locked |
| Hiding retry logic inside adapters | Simplifies the caller | Makes run-level recovery and observability inconsistent | Acceptable only for safe read-only calls |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Calendar adapter | Treating every retry as a fresh create | Use idempotency keys and reconcile external IDs |
| Task adapter | Mixing task normalization and external write logic | Separate normalized task artifacts from adapter-side mutation calls |
| Telegram approvals | Using message text as the source of truth | Persist approval requests and decisions in storage |
| LLM provider | Letting provider-specific response shapes leak into the kernel | Normalize provider outputs through typed Helm contracts |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Large unbounded artifact payloads | Slow reads and noisy status views | Persist concise normalized artifacts plus references to larger blobs if needed | Breaks once workflows accumulate many large artifacts |
| Poll-heavy approval loops | Worker churn and noisy logs | Separate paused runs from active execution scans | Breaks as paused runs accumulate |
| Overusing LLM calls for deterministic transforms | Higher latency and cost | Keep validation, state transitions, and adapter prep deterministic where possible | Breaks immediately on cost-sensitive repeated workflows |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logging full sensitive workflow payloads | Exposes personal or external-system data | Log identifiers, summaries, and status transitions by default |
| Allowing adapter writes without approval state checks | Unsafe external side effects | Enforce approval prerequisites in the kernel, not just UI |
| Trusting agent-produced external IDs or commands blindly | Corrupt writes or unsafe mutations | Validate adapter-bound payloads against typed schemas and decision context |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Approval requests lack concrete diff/context | User cannot approve confidently | Show proposed writes, affected systems, and revision options |
| Run status is too vague | User cannot tell whether the workflow is safe to ignore | Expose current step, last result, and next required action |
| Failure states are opaque | User loses trust quickly | Persist clear failure reason plus next recovery option |

## "Looks Done But Isn't" Checklist

- [ ] **Workflow run:** Often missing restart recovery — verify a process restart can resume an in-flight paused run.
- [ ] **Approval gate:** Often missing revise/edit support — verify approve, reject, and revision paths are all persisted.
- [ ] **Adapter write:** Often missing idempotency — verify a retried run does not duplicate external objects.
- [ ] **Artifact lineage:** Often missing invocation linkage — verify every artifact links back to run and step metadata.
- [ ] **Replay support:** Often missing partial recovery — verify failed runs can be inspected and resumed or retried intentionally.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Fake durability | HIGH | Backfill run state tables, add restart tests, and reconcile orphaned artifacts |
| Duplicate writes | HIGH | Add sync reconciliation, idempotency keys, and duplicate detection against external IDs |
| Approval as UI-only | MEDIUM | Introduce durable approval records and convert UI actions into run-state transitions |
| Unchecked agent output | MEDIUM | Insert validation layer, ambiguity flags, and typed artifact schemas before adapters |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Fake durability | Phase 1 | Restart an interrupted run and confirm exact step resume |
| Unchecked agent output | Phase 1 | Validate structured artifacts and reject malformed outputs |
| Kernel logic trapped in domains | Phase 2 | New workflow steps consume shared orchestration contracts |
| Approval as UI-only | Phase 2 | Pause, approve, reject, and revise all survive restart |
| Duplicate external writes | Phase 3 | Retries and replay do not create duplicate downstream objects |

## Sources

- LangGraph durable execution docs
- LangGraph human-in-the-loop docs
- Helm V1 spec in `docs/internal/helm-v1.md`
- Existing repo architecture and concerns maps in `.planning/codebase/`

---
*Pitfalls research for: durable orchestration kernel for Helm*
*Researched: 2026-03-11*
