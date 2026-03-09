from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from helm_connectors.gmail import NormalizedGmailMessage
from langgraph.graph import END, START, StateGraph


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


def _classify_message(_state: EmailTriageState) -> EmailTriageState:
    # TODO(v1-phase2-rhe15): replace with policy + LLM-assisted classification.
    return {"classification": "unclassified", "priority_score": 0}


def _summarize_thread(state: EmailTriageState) -> EmailTriageState:
    message = state["normalized_message"]
    if message.subject:
        summary = f"{message.from_address}: {message.subject}"
    elif message.body_text:
        summary = f"{message.from_address}: {message.body_text[:120]}"
    else:
        summary = f"{message.from_address}: (no subject/body)"
    return {"thread_summary": summary}


def _decide_artifacts(_state: EmailTriageState) -> EmailTriageState:
    # TODO(v1-phase2-rhe15): map classification/priority into artifact writes.
    return {
        "action_item_required": False,
        "draft_reply_required": False,
        "digest_item_required": False,
    }


def _finalize_state(_state: EmailTriageState) -> EmailTriageState:
    return {"workflow_status": "scaffold_completed"}


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
    message: NormalizedGmailMessage, *, graph: Any | None = None
) -> EmailTriageWorkflowResult:
    compiled_graph = graph or build_email_triage_graph()
    state = compiled_graph.invoke({"normalized_message": message})
    return EmailTriageWorkflowResult(
        message_id=message.provider_message_id,
        classification=state.get("classification", "unclassified"),
        priority_score=state.get("priority_score", 0),
        thread_summary=state.get("thread_summary", ""),
        action_item_required=state.get("action_item_required", False),
        draft_reply_required=state.get("draft_reply_required", False),
        digest_item_required=state.get("digest_item_required", False),
        workflow_status=state.get("workflow_status", "unknown"),
    )
