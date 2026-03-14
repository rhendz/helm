# Feature Research

**Domain:** Durable orchestration kernel for a personal AI workflow system
**Researched:** 2026-03-11
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Durable workflow runs | A kernel is not credible if runs disappear on restart or crash | HIGH | Requires persisted run state, step pointers, and replay-safe semantics |
| Step-level artifact persistence | Users need inspectable lineage, not opaque prompt memory | MEDIUM | Persist raw input, normalized outputs, validation results, approvals, and summaries |
| Human approval checkpoints | High-impact side effects need explicit approval in this repo's V1 contract | MEDIUM | Must support approve, reject, and revise/resubmit paths |
| Specialist-agent dispatch | The kernel must call distinct specialists cleanly | MEDIUM | Invocation records, typed inputs/outputs, and failure isolation matter |
| Adapter-based external writes | Side effects need clean boundaries and auditable results | MEDIUM | Task/calendar integrations should look like adapters, not arbitrary service calls |
| Failure handling and recovery | Long-running workflows fail in practice | HIGH | Persist retryability, error details, and resumable state transitions |
| Inspectable run status | Operator must know where a workflow is paused or failing | LOW | Telegram/API status surfaces are enough for V1 |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Typed plug-in specialist contract | Makes new agents easy to add without bespoke orchestration code | MEDIUM | Strong leverage for future Helm domains |
| Approval-aware resume semantics | Turns approval from a bolt-on into a first-class workflow state | HIGH | Important for Telegram-driven human supervision |
| Full side-effect lineage | Makes adapter writes debuggable and trustworthy | MEDIUM | External object IDs and sync results should be linked to the originating run |
| Replayable representative workflow demo | Proves the kernel is real, not just abstractions | MEDIUM | Weekly task-to-calendar scheduling is the right V1 demo |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Fully autonomous outbound actions | Feels impressive and faster | Violates repo safety principles and makes failures costly | Keep explicit approval before meaningful writes |
| Generic multi-tenant workflow platform | Feels future-proof | Distracts from personal-internal V1 and creates abstraction debt | Stay single-user and artifact-driven |
| Dashboard-heavy control plane | Feels operationally complete | Adds UI scope before the kernel contract is stable | Keep Telegram/API inspection for V1 |
| Too many specialist agents at once | Feels modular | Creates surface area before the orchestration contract is validated | Start with `TaskAgent` and `CalendarAgent` only |

## Feature Dependencies

```text
Durable workflow runs
    └──requires──> persisted workflow state
                          └──requires──> workflow schema + repositories

Approval checkpoints
    └──requires──> interrupt/resume model
                          └──requires──> persisted decision records

Adapter-based external writes
    └──requires──> validated artifacts
                          └──requires──> typed specialist outputs

Failure recovery
    └──enhances──> durable workflow runs

Autonomous side effects
    ──conflicts──> explicit approval gates
```

### Dependency Notes

- **Durable workflow runs require persisted workflow state:** without a durable run model, restart recovery is fake.
- **Approval checkpoints require interrupt/resume plus decisions:** pause alone is not enough; the system must record who decided what and resume deterministically.
- **Adapter writes require validated artifacts:** external systems should consume normalized, inspectable outputs rather than raw model text.
- **Failure recovery enhances durable runs:** retries, replay, and partial recovery should all build on the same persisted execution model.
- **Autonomous side effects conflict with approval gates:** the V1 kernel should not optimize away the human checkpoint.

## MVP Definition

### Launch With (v1)

- [ ] Durable workflow run lifecycle — essential because the kernel exists to survive restarts and failures
- [ ] Typed specialist invocation for `TaskAgent` and `CalendarAgent` — essential to prove the plug-in model
- [ ] Persisted artifacts at each major step — essential for lineage, debugging, and downstream writes
- [ ] Approval checkpoint with approve/reject/revise behavior — essential for safe external side effects
- [ ] Adapter-backed writes with sync records and external IDs — essential to keep boundaries clean
- [ ] One representative end-to-end scheduling workflow — essential to validate the kernel with a real sequence

### Add After Validation (v1.x)

- [ ] Generic replay tooling improvements — add once the base lifecycle is stable
- [ ] Richer operator commands for workflow inspection/editing — add when day-to-day usage reveals the gaps
- [ ] More specialist agent types — add after the first two prove the contract

### Future Consideration (v2+)

- [ ] More autonomous workflow branches — defer until approval semantics and failure recovery are proven safe
- [ ] Multiple concurrent domain workflows sharing the same kernel — defer until the first workflow pattern stabilizes
- [ ] Additional user surfaces beyond Telegram — defer until the operator model hardens

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Durable run lifecycle | HIGH | HIGH | P1 |
| Specialist dispatch contract | HIGH | MEDIUM | P1 |
| Approval checkpoints | HIGH | MEDIUM | P1 |
| Persisted artifacts and lineage | HIGH | MEDIUM | P1 |
| Adapter sync records | HIGH | MEDIUM | P1 |
| Representative scheduling demo | HIGH | MEDIUM | P1 |
| Rich replay tooling | MEDIUM | MEDIUM | P2 |
| Additional specialist types | MEDIUM | MEDIUM | P2 |
| New operator UI surfaces | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | Temporal-style systems | LangGraph-style systems | Our Approach |
|---------|------------------------|-------------------------|--------------|
| Durable execution | Strong workflow durability and replay | Built around graph persistence and interrupts | Use LangGraph-level durability with Helm-owned storage artifacts |
| Human approval | Usually custom application logic | First-class interrupt/resume support | Treat approval as a kernel state, not a one-off branch |
| Specialist tools/agents | Often activities/workers | Nodes, tasks, and tool-aware agents | Use typed specialist invocations with persisted artifacts |
| External side effects | Strong activity boundaries | Requires careful task/idempotency design | Put all side effects behind adapters plus sync records |

## Sources

- LangGraph durable execution docs
- LangGraph human-in-the-loop docs
- Helm product spec in `docs/internal/helm-v1.md`
- Existing Helm architecture map in `.planning/codebase/ARCHITECTURE.md`

---
*Feature research for: durable orchestration kernel for Helm*
*Researched: 2026-03-11*
