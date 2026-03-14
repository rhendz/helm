# T02: Reconciliation Policy Decision and Documentation

**Lock in reconciliation policy (passive), document decision and rationale, verify orchestration implementation matches, establish precedent for future recovery design.**

## Purpose

S02 detected drift; S04 must decide *how Helm responds*. This task locks in the reconciliation policy, documents the decision in DECISIONS.md with rationale and examples, and verifies the orchestration already implements the chosen policy. The decision shapes T01 (classification) and T03 (recovery actions).

## Must-Haves

- [ ] Reconciliation policy decided: passive (operator-initiated recovery) vs active (auto-propose) vs context-dependent
- [ ] Decision documented in DECISIONS.md with policy statement, rationale, examples, alternatives considered
- [ ] Orchestration implementation verified to match policy (no code changes needed if passive already implemented)
- [ ] Decision is unambiguous and referenced by other slices (T01, T03, S05)
- [ ] No requirements violated by chosen policy (R011 actually requires passive)

## Inputs

- S04 research section "1. Reconciliation Policy: Passive vs. Active"
- Existing M001 decision patterns in `.gsd/DECISIONS.md`
- R011 requirement statement: "Helm is an assistant, not an enforcer. Without this, Helm becomes adversarial and untrustworthy."
- Existing workflow_service.py _handle_drift_detected() implementation
- docs/internal/helm-v1.md for V1 scope constraints

## Expected Output

- Updated `.gsd/DECISIONS.md` with new decision entry:
  - Policy statement: clear, unambiguous, actionable
  - Rationale: why this choice over alternatives
  - Examples: concrete operator interaction (drift detection → recovery)
  - Alternatives: what was considered and why deferred
- Verification summary: orchestration already implements passive pattern (no code changes needed)
- Clarity for T03: what recovery actions are safe, what are deferred

## Steps

### 1. Review R011 requirement and existing philosophy
- Read `.gsd/REQUIREMENTS.md`, search for R011 (External-change detection and recovery)
  - Note: "Helm is an assistant, not an enforcer. Without this, Helm becomes adversarial and untrustworthy."
  - Implication: Helm should respect operator edits, not silently overwrite them
- Read `docs/internal/helm-v1.md` for V1 scope
  - Note: "Single user, personal internal system. Telegram-first UX for V1."
  - Implication: No complex automation; operator is the source of truth
- Read M001 decision examples in `.gsd/DECISIONS.md`
  - Pattern: "Explicit replay requests are validated against safe_next_actions"
  - Pattern: "Approval decisions now require concrete proposal artifact id so operator actions cannot silently resolve"
  - Observation: existing patterns favor explicit, operator-initiated actions

### 2. Analyze reconciliation policy options
- **Option A: Passive Reconciliation**
  - Helm detects drift, marks record, exposes [request_replay] action
  - Operator chooses to initiate recovery when ready
  - Pros: respects operator intent, simple (uses existing retry/replay mechanism), matches R011, no new proposal generation needed
  - Cons: requires operator awareness and action (slower recovery)
  - Alignment: matches M001 philosophy of explicit operator control

- **Option B: Active Reconciliation**
  - Helm detects drift, auto-generates new proposal (reshuffle), pauses workflow, waits for approval
  - Operator reviews proposal and approves/rejects
  - Pros: faster recovery, Helm can optimize reshuffle with updated calendar state
  - Cons: requires new proposal generation logic, UI design for approval, contradicts R011 (Helm fighting operator edits), higher implementation cost
  - Alignment: not justified for V1 (op heavy, not assistant behavior)

- **Option C: Context-Dependent**
  - Single event drift: passive (request_replay)
  - Schedule-level drift (multiple events): active (auto-propose reshuffle)
  - Pros: balances simplicity (single drift) with recovery speed (multi-event)
  - Cons: higher implementation cost, requires policy rules, harder to test, defers to future phases
  - Alignment: good for future optimization but too complex for V1

### 3. Make decision: Passive Reconciliation Policy
- Rationale:
  - R011 explicitly requires passive behavior (operator intent is ground truth)
  - Existing M001 patterns use operator-initiated recovery (retry, replay, terminate)
  - Simplest implementation: no new proposal generation needed, uses existing safe_next_actions pattern
  - Aligns with "assistant, not enforcer" philosophy
  - Operator can verify changes before initiating recovery
- Policy statement: "When drift is detected on a calendar event (operator manual edit), Helm marks the sync record as requiring recovery and exposes operator-initiated recovery actions (request_replay). Helm does not auto-generate new proposals or rewrite events. This respects operator intent and prevents adversarial behavior."
- Rationale summary: Passive reconciliation honors operator autonomy, uses proven recovery mechanisms, aligns with R011, and fits V1 scope.

### 4. Verify orchestration implementation matches passive policy
- Locate: `packages/orchestration/src/helm_orchestration/workflow_service.py`, method `_handle_drift_detected()`
- Read current implementation:
  - Extract field diffs
  - Log "drift_detected" signal
  - Create workflow event "drift_detected_external_change"
  - Mark sync record via mark_drift_detected()
  - **Continue to next record** (do not fail step, do not block workflow)
- Verify behavior matches passive pattern:
  - ✓ Drift is detected (not ignored)
  - ✓ Drift is recorded durably (workflow event, sync record)
  - ✓ Workflow continues (not blocked by drift)
  - ✓ Operator is informed (drift event created, record marked)
  - ✓ Recovery is operator-initiated (safe_next_actions will expose [request_replay] per T01)
- Conclusion: Orchestration already implements passive pattern. **No code changes needed in T02.**
- Observation: this is a design win — existing implementation already matches chosen policy

### 5. Document decision in DECISIONS.md
- Append new decision entry following existing pattern:
  ```
  - "Reconciliation policy: When drift is detected on calendar events, Helm adopts passive recovery (operator-initiated) rather than active (auto-propose). Helm marks drifted sync records as TERMINAL_FAILURE, exposes request_replay action, and continues workflow. This respects operator intent (R011: Helm is assistant, not enforcer) and uses proven M001 recovery mechanisms. Active reconciliation (auto-proposal generation) is deferred to future phases pending UI design and policy rules for context-dependent behavior."
  ```
- Include rationale:
  - "Passive pattern matches M001 philosophy: explicit operator control, durable recovery decisions"
  - "Eliminates risk of Helm fighting operator edits (R011 constraint)"
  - "Uses existing safe_next_actions + replay infrastructure (low implementation cost)"
  - "Operator can verify external state before initiating recovery (trust-building)"
- Include examples:
  - "Example: operator reschedules event 14:00→15:00 in Calendar → Helm detects drift at reconciliation → marks sync record DRIFT_DETECTED with field diffs → exposes [request_replay] → operator clicks to trigger replay with original Helm intent → new sync lineage created → reconciliation confirms event now at Helm's intended time"
  - "Example: operator cancels event → Helm detects drift → exposes [request_replay] → operator can choose to reschedule or leave cancelled (respects operator choice)"
- Include alternatives considered:
  - "Alternative 1 (Active): Auto-generate proposal after drift. Deferred due to implementation complexity (proposal generation rules, approval UI) and philosophical misalignment with R011."
  - "Alternative 2 (Context-dependent): Different policies for single-event vs schedule-level drift. Deferred to future phases pending policy rule design and test coverage."
- Include forward signal:
  - "If operator workflows create frequent manual edits and passive recovery becomes painful, revisit active reconciliation in future phases. Current polling latency (60 seconds per S02) is acceptable for passive model."

### 6. Verify no requirement violations
- Cross-check against R011: "Helm is an assistant, not an enforcer... Without this, Helm becomes adversarial and untrustworthy"
  - Passive policy respects operator edits ✓
  - Helm proposes [request_replay], operator chooses ✓
  - No silent rewrites ✓
  - **R011 satisfied**
- Cross-check against R012: "Real-time execution visibility in Telegram"
  - Drift detection is visible (event created, sync marked)
  - Recovery actions are visible ([request_replay] in safe_next_actions)
  - T03 will verify Telegram shows recovery options
  - **R012 supported**
- Cross-check against R013: "Operator trust through verification"
  - Passive recovery is simpler to test (fewer code paths)
  - Integration tests will prove drift detection → recovery path
  - UAT will show operator actual behavior
  - **R013 supported**
- Conclusion: No requirement violations. Policy is sound.

### 7. Cross-reference with T01 and T03
- T01 will use this decision: classification = TERMINAL_FAILURE, safe_next_actions = [request_replay]
- T03 will use this decision: integration tests will verify operator can initiate recovery via [request_replay]
- S05 will reference: UAT script will demonstrate passive recovery workflow
- No surprises; decision is aligned with downstream work

## Verification Checklist

- [ ] Reconciliation policy decided: **Passive** (operator-initiated recovery)
- [ ] Decision documented in DECISIONS.md with unambiguous policy statement
- [ ] Rationale explains why passive over alternatives (R011, M001 patterns, implementation cost)
- [ ] Examples show concrete operator interaction (drift → recovery action → recovery choice)
- [ ] Alternatives documented (active, context-dependent, with rationale for deferral)
- [ ] Orchestration implementation verified to match policy (no code changes in T02)
- [ ] No requirements violated (R011/R012/R013 all supported)
- [ ] Decision is actionable for T01 (classification rules) and T03 (test design)
- [ ] Forward signal included (when to reconsider, conditions for active policy)

## Done When

- T02 complete: Decision entry appended to DECISIONS.md, rationale clear, no code changes needed, T01/T03 have clear guidance.

