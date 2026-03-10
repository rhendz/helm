from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypedDict

from helm_connectors.gmail import NormalizedGmailMessage
from langgraph.graph import END, START, StateGraph

from email_agent.runtime import EmailAgentRuntime, build_runtime


class EmailTriageState(TypedDict, total=False):
    normalized_message: NormalizedGmailMessage
    classification: str
    priority_score: int
    thread_summary: str
    action_item_required: bool
    draft_reply_required: bool
    digest_item_required: bool
    workflow_status: str


@dataclass(slots=True, frozen=True)
class EmailTriageWorkflowResult:
    email_thread_id: int | None
    message_id: str
    classification: str
    priority_score: int
    thread_summary: str
    action_item_required: bool
    draft_reply_required: bool
    digest_item_required: bool
    workflow_status: str
    action_proposal_id: int | None = None
    email_draft_id: int | None = None
    action_item_id: int | None = None
    draft_reply_id: int | None = None
    digest_item_id: int | None = None


def _classify_message(state: EmailTriageState) -> EmailTriageState:
    message = state["normalized_message"]
    haystack = f"{message.subject}\n{message.body_text}".lower()

    if any(token in haystack for token in ("recruiter", "interview", "opportunity", "role")):
        return {"classification": "opportunity", "priority_score": 1}
    if any(token in haystack for token in ("urgent", "asap", "today", "deadline")):
        return {"classification": "urgent", "priority_score": 1}
    if any(token in haystack for token in ("newsletter", "unsubscribe")):
        return {"classification": "newsletter", "priority_score": 4}
    return {"classification": "unclassified", "priority_score": 3}


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
    action_required = classification in {"opportunity", "urgent"} or priority_score <= 2
    draft_required = classification in {"opportunity", "urgent"}
    digest_required = priority_score <= 2
    return {
        "action_item_required": action_required,
        "draft_reply_required": draft_required,
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
    message: NormalizedGmailMessage,
    *,
    graph: Any | None = None,
    session_factory: Callable[[], object] | None = None,
    runtime: EmailAgentRuntime | None = None,
) -> EmailTriageWorkflowResult:
    compiled_graph = graph or build_email_triage_graph()
    runtime_instance = runtime or build_runtime(session_factory=session_factory)

    run = runtime_instance.start_run(
        agent_name="email_triage",
        source_type="email_message",
        source_id=message.provider_message_id,
    )
    thread = runtime_instance.get_or_create_thread(provider_thread_id=message.provider_thread_id)
    thread_id = thread.id
    email_record = runtime_instance.upsert_inbound_message(
        message=message,
        email_thread_id=thread_id,
    )

    try:
        state = compiled_graph.invoke({"normalized_message": message})
        (
            action_proposal_id,
            email_draft_id,
            action_item_id,
            draft_reply_id,
            digest_item_id,
        ) = _persist_triage_artifacts(
            state=state,
            message=message,
            email_thread_id=thread_id,
            runtime=runtime_instance,
            email_message_id=email_record.id,
        )
        runtime_instance.mark_message_processed(
            message.provider_message_id,
            processed_at=datetime.now(tz=UTC),
        )
        runtime_instance.mark_run_succeeded(run.id)
    except Exception as exc:
        runtime_instance.mark_run_failed(run.id, str(exc))
        raise

    return EmailTriageWorkflowResult(
        email_thread_id=thread_id,
        message_id=message.provider_message_id,
        classification=state.get("classification", "unclassified"),
        priority_score=state.get("priority_score", 3),
        thread_summary=state.get("thread_summary", ""),
        action_item_required=state.get("action_item_required", False),
        draft_reply_required=state.get("draft_reply_required", False),
        digest_item_required=state.get("digest_item_required", False),
        workflow_status="completed",
        action_proposal_id=action_proposal_id,
        email_draft_id=email_draft_id,
        action_item_id=action_item_id,
        draft_reply_id=draft_reply_id,
        digest_item_id=digest_item_id,
    )


def _persist_triage_artifacts(
    *,
    state: EmailTriageState,
    message: NormalizedGmailMessage,
    email_thread_id: int,
    runtime: EmailAgentRuntime,
    email_message_id: int,
) -> tuple[int | None, int | None, int | None, int | None, int | None]:
    proposal_record = None
    email_draft_record = None
    action_record = None
    draft_record = None
    digest_record = None
    priority = _clamp_priority(state.get("priority_score", 3))
    thread_summary = state.get("thread_summary", "")
    classification = state.get("classification", "unclassified")
    action_reason = _derive_action_reason(state=state)
    visible_labels = _derive_visible_labels(state=state)
    business_state = _derive_business_state(state=state)
    confidence_band = _derive_confidence_band(
        priority_score=priority,
        classification=classification,
    )

    runtime.update_thread_state(
        email_thread_id,
        business_state=business_state,
        visible_labels=visible_labels,
        latest_confidence_band=confidence_band,
        resurfacing_source="new_message",
        action_reason=action_reason,
        current_summary=thread_summary or None,
        last_message_id=email_message_id,
        last_inbound_message_id=email_message_id,
    )

    if state.get("action_item_required", False):
        proposal_record = runtime.get_latest_proposal_for_thread(email_thread_id=email_thread_id)
        if proposal_record is None:
            proposal_record = runtime.create_proposal(
                email_thread_id=email_thread_id,
                proposal_type="reply" if state.get("draft_reply_required", False) else "review",
                rationale=thread_summary or None,
                confidence_band=confidence_band,
            )
        action_record = runtime.get_open_action_for_source(
            source_type="email_thread",
            source_id=message.provider_thread_id,
        )
        if action_record is None:
            action_record = runtime.get_open_action_for_source(
                source_type="email_message",
                source_id=message.provider_message_id,
            )
        if action_record is None:
            action_record = runtime.get_open_action_for_source(
                source_type="email_thread",
                source_id=message.provider_message_id,
            )
        if action_record is None:
            action_record = runtime.create_action(
                source_type="email_thread",
                source_id=message.provider_thread_id,
                title=_build_action_title(message),
                description=thread_summary or None,
                priority=priority,
            )

    if state.get("draft_reply_required", False):
        email_draft_record = runtime.get_latest_email_draft_for_thread(
            email_thread_id=email_thread_id
        )
        if email_draft_record is None:
            email_draft_record = runtime.create_email_draft(
                email_thread_id=email_thread_id,
                action_proposal_id=proposal_record.id if proposal_record is not None else None,
                draft_body=_build_draft_stub(message=message, classification=classification),
                draft_subject=message.subject or None,
            )
        draft_record = runtime.get_latest_legacy_draft_for_thread(
            thread_id=message.provider_thread_id
        )
        if draft_record is None:
            draft_record = runtime.create_legacy_draft_reply(
                thread_id=message.provider_thread_id,
                draft_text=_build_draft_stub(message=message, classification=classification),
            )

    if state.get("digest_item_required", False):
        digest_title = _build_digest_title(message)
        digest_summary = thread_summary or _build_fallback_summary(message)
        related_action_id = action_record.id if action_record is not None else None
        digest_record = runtime.find_matching_digest(
            domain="email",
            title=digest_title,
            summary=digest_summary,
            related_action_id=related_action_id,
        )
        if digest_record is None:
            digest_record = runtime.create_digest(
                domain="email",
                title=digest_title,
                summary=digest_summary,
                priority=priority,
                related_action_id=related_action_id,
            )

    action_proposal_id = proposal_record.id if proposal_record is not None else None
    email_draft_id = email_draft_record.id if email_draft_record is not None else None
    action_item_id = action_record.id if action_record is not None else None
    draft_reply_id = draft_record.id if draft_record is not None else None
    digest_item_id = digest_record.id if digest_record is not None else None
    return action_proposal_id, email_draft_id, action_item_id, draft_reply_id, digest_item_id


def _clamp_priority(value: int) -> int:
    return max(1, min(4, value))


def _build_action_title(message: NormalizedGmailMessage) -> str:
    subject = message.subject or "(no subject)"
    return f"Email follow-up: {subject[:200]}"


def _build_digest_title(message: NormalizedGmailMessage) -> str:
    subject = message.subject or "(no subject)"
    return f"Important email: {subject[:200]}"


def _build_fallback_summary(message: NormalizedGmailMessage) -> str:
    if message.subject:
        return f"{message.from_address}: {message.subject}"
    if message.body_text:
        return f"{message.from_address}: {message.body_text[:120]}"
    return f"{message.from_address}: (no subject/body)"


def _derive_business_state(*, state: EmailTriageState) -> str:
    if state.get("action_item_required", False):
        return "waiting_on_user"
    return "resolved"


def _derive_action_reason(*, state: EmailTriageState) -> str | None:
    if state.get("draft_reply_required", False):
        return "reply_needed"
    if state.get("action_item_required", False):
        return "awareness_needed"
    return None


def _derive_visible_labels(*, state: EmailTriageState) -> tuple[str, ...]:
    labels: list[str] = []
    if state.get("action_item_required", False):
        labels.append("Action")
    if state.get("classification") == "urgent":
        labels.append("Urgent")
    if state.get("classification") == "unclassified" and state.get("priority_score", 3) <= 2:
        labels.append("NeedsReview")
    return tuple(labels)


def _derive_confidence_band(*, priority_score: int, classification: str) -> str:
    if classification in {"opportunity", "urgent"} and priority_score <= 2:
        return "High"
    if classification == "unclassified":
        return "Medium"
    return "Low"


def _build_draft_stub(*, message: NormalizedGmailMessage, classification: str) -> str:
    subject = message.subject or "(no subject)"
    snippet = message.body_text[:240] if message.body_text else "(no body provided)"
    return (
        "Draft reply stub.\n\n"
        f"Thread: {message.provider_thread_id}\n"
        f"From: {message.from_address}\n"
        f"Subject: {subject}\n"
        f"Classification: {classification}\n\n"
        "Context snippet:\n"
        f"{snippet}\n\n"
        "TODO: personalize response and approve before sending."
    )
