from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from email_agent.runtime import EmailAgentRuntime
from email_agent.thread_state import transition_for_inbound
from email_agent.types import EmailMessage


class EmailTriageState(TypedDict, total=False):
    normalized_message: EmailMessage
    classification: str
    priority_score: int
    thread_summary: str
    should_surface: bool
    action_item_required: bool
    draft_reply_required: bool
    review_required: bool
    time_sensitive: bool
    digest_item_required: bool
    workflow_status: str


@dataclass(slots=True, frozen=True)
class EmailTriageWorkflowResult:
    email_thread_id: int | None
    message_id: str
    trigger_family: str
    classification: str
    priority_score: int
    thread_summary: str
    action_item_required: bool
    draft_reply_required: bool
    digest_item_required: bool
    workflow_status: str
    action_proposal_id: int | None = None
    email_draft_id: int | None = None
    digest_item_id: int | None = None


def _classify_message(state: EmailTriageState) -> EmailTriageState:
    message = state["normalized_message"]
    haystack = f"{message.subject}\n{message.body_text}".lower()
    time_sensitive = any(token in haystack for token in ("urgent", "asap", "today", "deadline"))

    if any(token in haystack for token in ("recruiter", "interview", "opportunity", "role")):
        return {
            "classification": "opportunity",
            "priority_score": 1,
            "time_sensitive": time_sensitive,
        }
    if any(token in haystack for token in ("review", "heads up", "fyi", "for your awareness")):
        return {
            "classification": "review",
            "priority_score": 2,
            "time_sensitive": time_sensitive,
        }
    if any(token in haystack for token in ("newsletter", "unsubscribe")):
        return {
            "classification": "newsletter",
            "priority_score": 4,
            "time_sensitive": False,
        }
    if time_sensitive or any(
        token in haystack for token in ("intro", "deck", "proposal", "founder", "investor")
    ):
        return {
            "classification": "unclassified",
            "priority_score": 2,
            "time_sensitive": time_sensitive,
        }
    return {
        "classification": "unclassified",
        "priority_score": 3,
        "time_sensitive": False,
    }


def _summarize_thread(state: EmailTriageState) -> EmailTriageState:
    message = state["normalized_message"]
    if message.subject:
        summary = f"{message.from_address}: {message.subject}"
    elif message.body_text:
        summary = f"{message.from_address}: {message.body_text[:120]}"
    else:
        summary = f"{message.from_address}: (no subject/body)"
    return {"thread_summary": summary}


def _decide_artifacts(state: EmailTriageState) -> EmailTriageState:
    classification = state.get("classification", "unclassified")
    priority_score = state.get("priority_score", 3)
    should_surface = classification != "newsletter" and priority_score <= 2
    review_required = classification == "unclassified" and should_surface
    action_required = should_surface and classification in {"opportunity", "review", "unclassified"}
    draft_required = should_surface and classification == "opportunity" and not review_required
    digest_required = should_surface and not review_required
    return {
        "should_surface": should_surface,
        "action_item_required": action_required,
        "draft_reply_required": draft_required,
        "review_required": review_required,
        "time_sensitive": state.get("time_sensitive", False),
        "digest_item_required": digest_required,
    }


def _finalize_state(_state: EmailTriageState) -> EmailTriageState:
    return {"workflow_status": "classified"}


def build_email_triage_graph() -> Any:
    graph = StateGraph(EmailTriageState)
    graph.add_node("classify_message", _classify_message)
    graph.add_node("summarize_thread", _summarize_thread)
    graph.add_node("decide_artifacts", _decide_artifacts)
    graph.add_node("finalize_state", _finalize_state)

    graph.add_edge(START, "classify_message")
    graph.add_edge("classify_message", "summarize_thread")
    graph.add_edge("summarize_thread", "decide_artifacts")
    graph.add_edge("decide_artifacts", "finalize_state")
    graph.add_edge("finalize_state", END)
    return graph.compile()


def run_email_triage_workflow(
    message: EmailMessage,
    *,
    graph: Any | None = None,
    runtime: EmailAgentRuntime,
    trigger_family: str = "inbound_email",
) -> EmailTriageWorkflowResult:
    compiled_graph = graph or build_email_triage_graph()

    run = runtime.start_run(
        agent_name="email_triage",
        source_type="email_message",
        source_id=message.provider_message_id,
    )
    thread = runtime.get_or_create_thread(provider_thread_id=message.provider_thread_id)
    thread_id = thread.id
    email_record = runtime.upsert_inbound_message(
        message=message,
        email_thread_id=thread_id,
    )

    try:
        state = compiled_graph.invoke({"normalized_message": message})
        (
            action_proposal_id,
            email_draft_id,
            digest_item_id,
        ) = _persist_triage_artifacts(
            state=state,
            message=message,
            email_thread_id=thread_id,
            runtime=runtime,
            email_message_id=email_record.id,
            trigger_family=trigger_family,
        )
        runtime.mark_message_processed(
            message.provider_message_id,
            processed_at=datetime.now(tz=UTC),
        )
        runtime.mark_run_succeeded(run.id)
    except Exception as exc:
        runtime.mark_run_failed(run.id, str(exc))
        raise

    return EmailTriageWorkflowResult(
        email_thread_id=thread_id,
        message_id=message.provider_message_id,
        trigger_family=trigger_family,
        classification=state.get("classification", "unclassified"),
        priority_score=state.get("priority_score", 3),
        thread_summary=state.get("thread_summary", ""),
        action_item_required=state.get("action_item_required", False),
        draft_reply_required=state.get("draft_reply_required", False),
        digest_item_required=state.get("digest_item_required", False),
        workflow_status="completed",
        action_proposal_id=action_proposal_id,
        email_draft_id=email_draft_id,
        digest_item_id=digest_item_id,
    )


def _persist_triage_artifacts(
    *,
    state: EmailTriageState,
    message: EmailMessage,
    email_thread_id: int,
    runtime: EmailAgentRuntime,
    email_message_id: int,
    trigger_family: str,
) -> tuple[int | None, int | None, int | None]:
    proposal_record = None
    email_draft_record = None
    digest_record = None
    priority = _clamp_priority(state.get("priority_score", 3))
    thread_summary = state.get("thread_summary", "")
    classification = state.get("classification", "unclassified")
    existing_thread = runtime.get_thread_by_id(email_thread_id)
    thread_update = transition_for_inbound(
        classification=classification,
        priority_score=priority,
        thread_summary=thread_summary or None,
        should_surface=state.get("should_surface", False),
        action_item_required=state.get("action_item_required", False),
        draft_reply_required=state.get("draft_reply_required", False),
        review_required=state.get("review_required", False),
        time_sensitive=state.get("time_sensitive", False),
        email_message_id=email_message_id,
        previous_thread=existing_thread,
    )

    runtime.update_thread_state(
        email_thread_id,
        business_state=thread_update.business_state,
        visible_labels=thread_update.visible_labels,
        latest_confidence_band=thread_update.latest_confidence_band,
        resurfacing_source=thread_update.resurfacing_source,
        action_reason=thread_update.action_reason,
        current_summary=thread_update.current_summary,
        last_message_id=thread_update.last_message_id,
        last_inbound_message_id=thread_update.last_inbound_message_id,
        last_outbound_message_id=thread_update.last_outbound_message_id,
    )
    runtime.create_classification_artifact(
        email_thread_id=email_thread_id,
        email_message_id=email_message_id,
        classification=classification,
        priority_score=priority,
        business_state=thread_update.business_state,
        visible_labels=thread_update.visible_labels,
        action_reason=thread_update.action_reason,
        resurfacing_source=thread_update.resurfacing_source,
        confidence_band=thread_update.latest_confidence_band,
        decision_context={
            "trigger_family": trigger_family,
            "should_surface": state.get("should_surface", False),
            "action_item_required": state.get("action_item_required", False),
            "draft_reply_required": state.get("draft_reply_required", False),
            "review_required": state.get("review_required", False),
            "time_sensitive": state.get("time_sensitive", False),
            "digest_item_required": state.get("digest_item_required", False),
            "thread_summary": thread_summary,
        },
        model_name="rule_based_triage",
        prompt_version="email_triage_v1",
    )

    if state.get("action_item_required", False):
        proposal_record = runtime.get_latest_proposal_for_thread(email_thread_id=email_thread_id)
        if proposal_record is None:
            proposal_type = "review"
            if state.get("draft_reply_required", False):
                proposal_type = "reply"
            proposal_record = runtime.create_proposal(
                email_thread_id=email_thread_id,
                proposal_type=proposal_type,
                rationale=thread_summary or None,
                confidence_band=thread_update.latest_confidence_band,
            )

    if state.get("draft_reply_required", False):
        email_draft_record = runtime.get_latest_email_draft_for_thread(
            email_thread_id=email_thread_id
        )
        draft_body = _build_grounded_draft_reply(message=message, classification=classification)
        reasoning_artifact = {
            "schema_version": "email_draft_reasoning_v1",
            "prompt_context": {
                "trigger_family": trigger_family,
                "thread_summary": thread_summary,
                "from_address": message.from_address,
                "subject": message.subject,
                "body_text": message.body_text,
            },
            "model_metadata": {
                "generator": "deterministic_grounded_reply",
                "prompt_version": "email_draft_grounded_v1",
            },
            "reasoning_payload": {
                "classification": classification,
                "draft_reply_required": state.get("draft_reply_required", False),
                "action_item_required": state.get("action_item_required", False),
                "grounding_signals": _draft_grounding_signals(message),
            },
            "refinement_metadata": {
                "event_type": "refinement" if email_draft_record is not None else "generation",
                "strategy": "deterministic_grounded_reply",
            },
        }
        if email_draft_record is None:
            email_draft_record = runtime.create_email_draft(
                email_thread_id=email_thread_id,
                action_proposal_id=proposal_record.id if proposal_record is not None else None,
                draft_body=draft_body,
                draft_subject=message.subject or None,
                reasoning_artifact=reasoning_artifact,
            )
        else:
            email_draft_record = runtime.update_email_draft(
                draft_id=email_draft_record.id,
                email_thread_id=email_thread_id,
                action_proposal_id=proposal_record.id if proposal_record is not None else None,
                draft_body=draft_body,
                draft_subject=message.subject or None,
                reasoning_artifact=reasoning_artifact,
            )

    if state.get("digest_item_required", False):
        digest_title = _build_digest_title(message)
        digest_summary = thread_summary or _build_fallback_summary(message)
        digest_record = runtime.find_matching_digest(
            domain="email",
            title=digest_title,
            summary=digest_summary,
        )
        if digest_record is None:
            digest_record = runtime.create_digest(
                domain="email",
                title=digest_title,
                summary=digest_summary,
                priority=priority,
            )

    action_proposal_id = proposal_record.id if proposal_record is not None else None
    email_draft_id = email_draft_record.id if email_draft_record is not None else None
    digest_item_id = digest_record.id if digest_record is not None else None
    return action_proposal_id, email_draft_id, digest_item_id


def _clamp_priority(value: int) -> int:
    return max(1, min(4, value))


def process_inbound_email_message(
    message: EmailMessage,
    *,
    graph: Any | None = None,
    runtime: EmailAgentRuntime,
) -> EmailTriageWorkflowResult:
    existing_thread = runtime.get_thread_by_provider_thread_id(message.provider_thread_id)
    trigger_family = (
        "existing_thread_inbound" if existing_thread is not None else "new_thread_inbound"
    )
    return run_email_triage_workflow(
        message,
        graph=graph,
        runtime=runtime,
        trigger_family=trigger_family,
    )


def _build_digest_title(message: EmailMessage) -> str:
    subject = message.subject or "(no subject)"
    return f"Important email: {subject[:200]}"


def _build_fallback_summary(message: EmailMessage) -> str:
    if message.subject:
        return f"{message.from_address}: {message.subject}"
    if message.body_text:
        return f"{message.from_address}: {message.body_text[:120]}"
    return f"{message.from_address}: (no subject/body)"


def _build_grounded_draft_reply(*, message: EmailMessage, classification: str) -> str:
    lines = ["Thanks for reaching out."]

    if classification == "opportunity":
        lines.append("I'm interested in learning more about this opportunity.")
    else:
        lines.append("I wanted to follow up on your note.")

    if _has_scheduling_cue(message):
        lines.append(
            "I'd be glad to chat. If you send over a few times that work on your side, "
            "I can confirm one."
        )
    elif _has_detail_request_cue(message):
        lines.append("Please share the relevant details and next steps when you can.")
    else:
        lines.append("Please let me know the best next step from here.")

    return "\n\n".join(lines)


def _draft_grounding_signals(message: EmailMessage) -> dict[str, bool]:
    return {
        "has_scheduling_cue": _has_scheduling_cue(message),
        "has_detail_request_cue": _has_detail_request_cue(message),
        "has_subject": bool(message.subject.strip()),
        "has_body_text": bool(message.body_text.strip()),
    }


def _has_scheduling_cue(message: EmailMessage) -> bool:
    haystack = f"{message.subject}\n{message.body_text}".lower()
    return any(
        token in haystack
        for token in ("interview", "chat", "call", "availability", "times", "this week")
    )


def _has_detail_request_cue(message: EmailMessage) -> bool:
    haystack = f"{message.subject}\n{message.body_text}".lower()
    return any(
        token in haystack
        for token in ("details", "next steps", "learn more", "share more", "role")
    )
