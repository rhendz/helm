from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EmailTriageStep(StrEnum):
    MESSAGE_INGESTED = "message_ingested"
    MESSAGE_STORED = "message_stored"
    EMAIL_CLASSIFIED = "email_classified"
    THREAD_SUMMARIZED = "thread_summarized"
    ACTION_ITEM_UPSERTED = "action_item_upserted"
    DRAFT_GENERATED = "draft_generated"
    DIGEST_ITEM_CREATED = "digest_item_created"
    TELEGRAM_NOTIFIED = "telegram_notified"
    AGENT_RUN_LOGGED = "agent_run_logged"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class WorkflowHandoff:
    target: str
    payload: dict[str, Any]


@dataclass(slots=True)
class EmailTriageState:
    provider_message_id: str
    provider_thread_id: str
    step: EmailTriageStep = EmailTriageStep.MESSAGE_INGESTED
    category: str | None = None
    priority_score: int | None = None
    thread_summary: str | None = None
    should_create_action_item: bool = True
    should_generate_draft: bool = False
    should_create_digest_item: bool = False
    should_notify_telegram: bool = False
    error_message: str | None = None
    handoffs: list[WorkflowHandoff] = field(default_factory=list)


def build_email_triage_graph() -> dict[EmailTriageStep, EmailTriageStep]:
    """Return the linear transition map used by the email triage scaffold."""
    # TODO(rhe-15): convert this map into a compiled LangGraph once node handlers are implemented.
    return {
        EmailTriageStep.MESSAGE_INGESTED: EmailTriageStep.MESSAGE_STORED,
        EmailTriageStep.MESSAGE_STORED: EmailTriageStep.EMAIL_CLASSIFIED,
        EmailTriageStep.EMAIL_CLASSIFIED: EmailTriageStep.THREAD_SUMMARIZED,
        EmailTriageStep.THREAD_SUMMARIZED: EmailTriageStep.ACTION_ITEM_UPSERTED,
        EmailTriageStep.ACTION_ITEM_UPSERTED: EmailTriageStep.DRAFT_GENERATED,
        EmailTriageStep.DRAFT_GENERATED: EmailTriageStep.DIGEST_ITEM_CREATED,
        EmailTriageStep.DIGEST_ITEM_CREATED: EmailTriageStep.TELEGRAM_NOTIFIED,
        EmailTriageStep.TELEGRAM_NOTIFIED: EmailTriageStep.AGENT_RUN_LOGGED,
        EmailTriageStep.AGENT_RUN_LOGGED: EmailTriageStep.COMPLETED,
    }


def run_email_triage_workflow(initial_state: EmailTriageState) -> EmailTriageState:
    """Execute state transitions and emit handoff events for downstream modules."""
    state = initial_state
    transition_map = build_email_triage_graph()
    guard_limit = 20

    while state.step not in {EmailTriageStep.COMPLETED, EmailTriageStep.FAILED} and guard_limit > 0:
        _emit_handoff_for_step(state)
        next_step = transition_map.get(state.step)
        if next_step is None:
            current_step = state.step
            state.step = EmailTriageStep.FAILED
            state.error_message = f"No transition defined for step={current_step.value}"
            break
        state.step = next_step
        guard_limit -= 1

    if guard_limit == 0 and state.step not in {EmailTriageStep.COMPLETED, EmailTriageStep.FAILED}:
        state.step = EmailTriageStep.FAILED
        state.error_message = "Transition guard limit exceeded"
    return state


def _emit_handoff_for_step(state: EmailTriageState) -> None:
    if state.step == EmailTriageStep.MESSAGE_INGESTED:
        state.handoffs.append(
            WorkflowHandoff(
                target="storage.persist_email_message",
                payload={
                    "provider_message_id": state.provider_message_id,
                    "provider_thread_id": state.provider_thread_id,
                },
            )
        )
        return

    if state.step == EmailTriageStep.MESSAGE_STORED:
        state.handoffs.append(
            WorkflowHandoff(
                target="agents.email.classify",
                payload={
                    "provider_message_id": state.provider_message_id,
                    "provider_thread_id": state.provider_thread_id,
                },
            )
        )
        return

    if state.step == EmailTriageStep.EMAIL_CLASSIFIED:
        state.handoffs.append(
            WorkflowHandoff(
                target="storage.upsert_email_thread_summary",
                payload={
                    "provider_thread_id": state.provider_thread_id,
                    "summary": state.thread_summary,
                    "category": state.category,
                    "priority_score": state.priority_score,
                },
            )
        )
        return

    if state.step == EmailTriageStep.THREAD_SUMMARIZED:
        if state.should_create_action_item:
            state.handoffs.append(
                WorkflowHandoff(
                    target="storage.upsert_action_item",
                    payload={"provider_thread_id": state.provider_thread_id},
                )
            )
        return

    if state.step == EmailTriageStep.ACTION_ITEM_UPSERTED:
        if state.should_generate_draft:
            state.handoffs.append(
                WorkflowHandoff(
                    target="agents.email.generate_draft",
                    payload={"provider_thread_id": state.provider_thread_id},
                )
            )
            state.handoffs.append(
                WorkflowHandoff(
                    target="storage.create_draft_reply",
                    payload={"provider_thread_id": state.provider_thread_id},
                )
            )
        return

    if state.step == EmailTriageStep.DRAFT_GENERATED:
        if state.should_create_digest_item:
            state.handoffs.append(
                WorkflowHandoff(
                    target="storage.create_digest_item",
                    payload={"provider_thread_id": state.provider_thread_id},
                )
            )
        return

    if state.step == EmailTriageStep.DIGEST_ITEM_CREATED:
        if state.should_notify_telegram:
            state.handoffs.append(
                WorkflowHandoff(
                    target="apps.telegram.notify_high_priority",
                    payload={"provider_thread_id": state.provider_thread_id},
                )
            )
        return

    if state.step == EmailTriageStep.AGENT_RUN_LOGGED:
        state.handoffs.append(
            WorkflowHandoff(
                target="observability.log_agent_run",
                payload={
                    "agent_name": "email_triage",
                    "provider_message_id": state.provider_message_id,
                    "status": "completed",
                },
            )
        )
