from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypedDict

from helm_connectors.gmail import NormalizedGmailMessage
from helm_storage.db import SessionLocal
from helm_storage.repositories.action_items import SQLAlchemyActionItemRepository
from helm_storage.repositories.agent_runs import SQLAlchemyAgentRunRepository
from helm_storage.repositories.contracts import NewActionItem, NewDigestItem, NewDraftReply
from helm_storage.repositories.digest_items import SQLAlchemyDigestItemRepository
from helm_storage.repositories.draft_replies import SQLAlchemyDraftReplyRepository
from helm_storage.repositories.email_messages import SQLAlchemyEmailMessageRepository
from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session


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
    message_id: str
    classification: str
    priority_score: int
    thread_summary: str
    action_item_required: bool
    draft_reply_required: bool
    digest_item_required: bool
    workflow_status: str
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
    session_factory: Callable[[], Session] | None = None,
) -> EmailTriageWorkflowResult:
    compiled_graph = graph or build_email_triage_graph()
    open_session = session_factory or SessionLocal

    with open_session() as session:
        email_repo = SQLAlchemyEmailMessageRepository(session)
        action_repo = SQLAlchemyActionItemRepository(session)
        draft_repo = SQLAlchemyDraftReplyRepository(session)
        digest_repo = SQLAlchemyDigestItemRepository(session)
        run_repo = SQLAlchemyAgentRunRepository(session)

        run = run_repo.start_run(
            agent_name="email_triage",
            source_type="email_message",
            source_id=message.provider_message_id,
        )
        email_repo.upsert_from_normalized(message)

        try:
            state = compiled_graph.invoke({"normalized_message": message})
            action_item_id, draft_reply_id, digest_item_id = _persist_triage_artifacts(
                state=state,
                message=message,
                action_repo=action_repo,
                draft_repo=draft_repo,
                digest_repo=digest_repo,
            )
            email_repo.mark_processed(
                message.provider_message_id,
                processed_at=datetime.now(tz=UTC),
            )
            run_repo.mark_succeeded(run.id)
        except Exception as exc:
            run_repo.mark_failed(run.id, str(exc))
            raise

    return EmailTriageWorkflowResult(
        message_id=message.provider_message_id,
        classification=state.get("classification", "unclassified"),
        priority_score=state.get("priority_score", 3),
        thread_summary=state.get("thread_summary", ""),
        action_item_required=state.get("action_item_required", False),
        draft_reply_required=state.get("draft_reply_required", False),
        digest_item_required=state.get("digest_item_required", False),
        workflow_status="completed",
        action_item_id=action_item_id,
        draft_reply_id=draft_reply_id,
        digest_item_id=digest_item_id,
    )


def _persist_triage_artifacts(
    *,
    state: EmailTriageState,
    message: NormalizedGmailMessage,
    action_repo: SQLAlchemyActionItemRepository,
    draft_repo: SQLAlchemyDraftReplyRepository,
    digest_repo: SQLAlchemyDigestItemRepository,
) -> tuple[int | None, int | None, int | None]:
    action_record = None
    draft_record = None
    digest_record = None
    priority = _clamp_priority(state.get("priority_score", 3))
    thread_summary = state.get("thread_summary", "")
    classification = state.get("classification", "unclassified")

    if state.get("action_item_required", False):
        action_record = action_repo.get_open_by_source(
            source_type="email_message",
            source_id=message.provider_message_id,
        )
        if action_record is None:
            action_record = action_repo.create(
                NewActionItem(
                    source_type="email_message",
                    source_id=message.provider_message_id,
                    title=_build_action_title(message),
                    description=thread_summary or None,
                    priority=priority,
                )
            )

    if state.get("draft_reply_required", False):
        draft_record = draft_repo.get_latest_for_thread(thread_id=message.provider_thread_id)
        if draft_record is None:
            draft_record = draft_repo.create(
                NewDraftReply(
                    channel_type="email",
                    thread_id=message.provider_thread_id,
                    draft_text=_build_draft_stub(message=message, classification=classification),
                    tone="professional",
                    status="pending",
                )
            )

    if state.get("digest_item_required", False):
        digest_title = _build_digest_title(message)
        digest_summary = thread_summary or _build_fallback_summary(message)
        related_action_id = action_record.id if action_record is not None else None
        digest_record = digest_repo.find_matching(
            domain="email",
            title=digest_title,
            summary=digest_summary,
            related_action_id=related_action_id,
        )
        if digest_record is None:
            digest_record = digest_repo.create(
                NewDigestItem(
                    domain="email",
                    title=digest_title,
                    summary=digest_summary,
                    priority=priority,
                    related_action_id=related_action_id,
                )
            )

    action_item_id = action_record.id if action_record is not None else None
    draft_reply_id = draft_record.id if draft_record is not None else None
    digest_item_id = digest_record.id if digest_record is not None else None
    return action_item_id, draft_reply_id, digest_item_id


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
