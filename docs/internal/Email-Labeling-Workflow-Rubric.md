# Email Labeling Workflow And Confidence Routing Rubric

Primary references:
- `/Users/ankush/Downloads/email-agent-system-definition.md`
- [EmailAgentPolicy.md](/Users/ankush/git/helm/docs/internal/EmailAgentPolicy.md)
- [email-agent-blocked-slices-and-decisions.md](/Users/ankush/git/helm/docs/internal/email-agent-blocked-slices-and-decisions.md)

This document defines the operational labeling and confidence-routing rubric for the Email Agent.

It specifies how to determine:
- whether a thread should surface
- thread business state
- visible labels
- action reason
- confidence routing behavior

## Output Model

The classifier must emit explicit outputs:
- `should_surface`
- `business_state`
- `visible_labels`
- `action_reason`
- `confidence_band`

Confidence is a routing aid.
It is not a downstream substitute for explicit state or label decisions.

## Surface Or Suppress

### Suppress

Suppress when the email is clearly low-signal.

Typical low-signal cases:
- newsletters
- obvious bulk mail
- low-value automated notices
- clearly ignorable promotional mail

Suppressed threads:
- do not surface
- keep visible labels empty

### Surface

Surface when:
- the email is actionable
- the email is important
- the email is time-sensitive
- the email is uncertain but potentially important
- the email requires human judgment

When uncertain between surfacing and suppressing:
- prefer surfacing

## Visible Label Semantics

The visible label set in v1 is:
- `Action`
- `Urgent`
- `NeedsReview`

### `Action`

Apply `Action` when:
- the thread is surfaced
- action is needed from the user
- the thread is not review-blocked

Important:
- `Action` is independent of draft existence
- a thread may be `Action` even if no draft exists
- a draft failure must not suppress `Action`

### `Urgent`

Apply `Urgent` when:
- the thread is surfaced
- the thread is time-sensitive
- the thread is not review-blocked

`Urgent` only exists on surfaced threads.

### `NeedsReview`

Apply `NeedsReview` when the thread is surfaced and human review is required.

This includes:
- classifier uncertainty
- ambiguity that should not be resolved automatically
- cases where the system is confident the thread matters but a human judgment call is still needed

`NeedsReview` is exclusive.

If `NeedsReview` is present:
- do not also apply `Action`
- do not also apply `Urgent`

## Allowed Label Combinations

Allowed visible-label outcomes:
- no labels for suppressed low-signal threads
- `Action`
- `Action` + `Urgent`
- `NeedsReview`

Disallowed combinations:
- `NeedsReview` + `Action`
- `NeedsReview` + `Urgent`

## Business-State Routing

The classifier should map surfaced threads into explicit business state.

High-level guidance:
- `needs_review` when review is required
- `waiting_on_user` when the user owes action/response
- `waiting_on_other_party` when the user is waiting on someone else
- `resolved` when no further surfaced work remains
- `uninitialized` is an implementation/bootstrap state, not the normal output target for mature classification

## Confidence Routing

Confidence influences routing before final state/labels are emitted.

Rule:
- low confidence on a potentially important email should route to `NeedsReview`

Do not:
- emit `Action` and expect downstream logic to reinterpret low confidence later

Do:
- emit the explicit final review outcome directly

In practical terms:
- low confidence + potentially important => `NeedsReview`
- high enough confidence + actionable => `Action`
- high enough confidence + actionable + time-sensitive => `Action` + `Urgent`

## Fallback Behavior

Target design:
- primary path is LLM/rubric-driven classification
- heuristic classification is fallback only

Implications:
- heuristic fallback should preserve the same operator semantics as the target rubric
- heuristic classification should not allow label combinations the rubric disallows
- transitional heuristic artifacts are not the target reasoning contract

## Action Reason

`action_reason` should describe why the thread surfaced operationally.

Examples:
- `reply_needed`
- `followup_due`
- `reminder_due`
- `awareness_needed`
- `user_requested_review`

`action_reason` is separate from:
- visible labels
- draft existence
- execution status
