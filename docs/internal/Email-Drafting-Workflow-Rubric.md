# Email Drafting Workflow And Refinement Rubric

Primary references:
- `/Users/ankush/Downloads/email-agent-system-definition.md`
- [EmailAgentPolicy.md](/Users/ankush/git/helm/docs/internal/EmailAgentPolicy.md)
- [email-agent-blocked-slices-and-decisions.md](/Users/ankush/git/helm/docs/internal/email-agent-blocked-slices-and-decisions.md)

This document defines when the Email Agent drafts, how drafts evolve, and how refinement interacts with approval and sending.

## Drafting Entry Rule

Do not generate a draft for every actionable thread.

Generate a draft only when reply drafting is explicitly needed.

That decision should come from the proposal/classification path, not from a generic “actionable implies draft” shortcut.

This preserves:
- proposal-only paths
- review-only paths
- action visibility even when draft generation fails

## V1 Draft Generation Shape

V1 generates a single best draft.

It does not generate multiple candidate drafts for user choice.

If the user wants refinement:
- the user can converse with the agent
- the same draft lifecycle continues

## Draft Identity

One draft lifecycle should use one `EmailDraft` record.

Refinements/regenerations:
- update the draft in place
- preserve stable draft identity for approval and send lineage

Do not create a new `EmailDraft` row for every refinement.

## Approval Rule

Approval is attached to exact content.

Implications:
- an approved draft remains approved if transport fails and content is unchanged
- if draft content changes materially, approval must reset
- changed content must be re-approved before send

## `send_failed` Behavior

`send_failed` means:
- delivery did not complete successfully for the current draft lifecycle

It does not imply:
- the draft content was bad
- the draft caused the failure

`send_failed` drafts remain refinable.

User options after `send_failed`:
- retry the same unchanged draft
- refine the draft
- re-approve changed content
- send again

Rules:
- unchanged retry may reuse prior approval
- changed content resets approval

## Draft Reasoning Artifacts

Draft reasoning artifacts are for LLM-related drafting and refinement events.

They are:
- separate from operational draft truth
- document-style artifacts
- versioned with required `schema_version`
- stored in a dedicated artifact family/table

Each draft generation or refinement event creates a new reasoning artifact.

Do not collapse artifact history down to only the final event.

## Artifact Linkage

Draft reasoning artifacts should link to:
- `email_draft_id`
- `action_proposal_id` when present
- `email_thread_id`

This supports:
- future memory analysis
- refinement-history study
- proposal-to-draft-to-send lineage analysis

## Artifact Payload Guidance

Draft reasoning artifacts should capture rich LLM-related payloads, including:
- prompt/context snapshot
- model metadata
- structured reasoning output
- refinement-stage metadata
- schema version

They should not become a generic dump of unrelated operational logs.

## Drafting Quality Guidance

Drafts should optimize for:
- usefulness
- correctness
- groundedness

over:
- polish
- flourish
- unnecessary stylistic variation

The Email Agent should not invent:
- thread facts
- commitments
- scheduling promises
- relationship assumptions

without grounding in thread context, explicit user instruction, or allowed memory.

## Context Priority

Thread-local context outranks generalized memory.

Memory may shape:
- tone
- style
- phrasing

Memory must not override:
- explicit facts in the thread
- explicit user instructions

## Insufficient Context Rule

When context is insufficient for a confident draft:
- prefer surfacing for review
- do not bluff through missing context

This rule overrides any urge to produce a polished but weakly grounded draft.
