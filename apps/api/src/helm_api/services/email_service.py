from collections.abc import Mapping
from dataclasses import asdict

from email_agent.adapters import build_helm_runtime
from email_agent.query import (
    get_email_thread_detail,
    list_email_drafts,
    list_email_proposals,
    list_email_threads,
)
from email_agent.reminders import (
    complete_thread_task,
    create_thread_reminder,
    list_thread_scheduled_tasks,
)
from email_agent.reprocess import reprocess_email_thread
from email_agent.triage import build_email_triage_graph, run_email_triage_workflow
from email_agent.types import EmailMessage
from helm_connectors.gmail import pull_new_messages_report
from helm_observability.agent_runs import record_agent_run
from sqlalchemy.exc import SQLAlchemyError


def _runtime():
    return build_helm_runtime()


def list_threads(*, limit: int = 20) -> list[dict]:
    return list_email_threads(limit=limit, runtime=_runtime())


def list_proposals(*, limit: int = 20) -> list[dict]:
    return list_email_proposals(limit=limit, runtime=_runtime())


def list_drafts(*, limit: int = 20) -> list[dict]:
    return list_email_drafts(limit=limit, runtime=_runtime())


def get_thread_detail(*, thread_id: int) -> dict | None:
    return get_email_thread_detail(thread_id=thread_id, runtime=_runtime())


def reprocess_thread(*, thread_id: int, dry_run: bool) -> dict:
    return asdict(
        reprocess_email_thread(
            thread_id=thread_id,
            dry_run=dry_run,
            runtime=_runtime(),
        )
    )


def override_thread(
    *,
    thread_id: int,
    business_state: str,
    visible_labels: list[str],
    current_summary: str | None,
    latest_confidence_band: str | None,
    action_reason: str | None,
) -> dict:
    runtime = _runtime()
    try:
        thread = runtime.get_thread_by_id(thread_id)
        detail = runtime.get_email_thread_detail(thread_id=thread_id)
    except SQLAlchemyError:
        return {
            "status": "unavailable",
            "thread_id": thread_id,
            "found": False,
            "reason": "storage_unavailable",
            "thread": None,
        }
    if thread is None or detail is None:
        return {
            "status": "not_found",
            "thread_id": thread_id,
            "found": False,
            "reason": "thread_not_found",
            "thread": None,
        }

    try:
        updated = runtime.update_thread_state(
            thread_id,
            business_state=business_state,
            visible_labels=tuple(visible_labels),
            latest_confidence_band=latest_confidence_band,
            resurfacing_source="user_override",
            action_reason=action_reason,
            current_summary=current_summary,
            last_message_id=thread.last_message_id,
            last_inbound_message_id=thread.last_inbound_message_id,
            last_outbound_message_id=thread.last_outbound_message_id,
        )
    except SQLAlchemyError:
        return {
            "status": "unavailable",
            "thread_id": thread_id,
            "found": False,
            "reason": "storage_unavailable",
            "thread": None,
        }
    if updated is None:
        return {
            "status": "not_found",
            "thread_id": thread_id,
            "found": False,
            "reason": "thread_not_found",
            "thread": None,
        }
    return {
        "status": "accepted",
        "thread_id": thread_id,
        "found": True,
        "reason": None,
        "thread": {
            "id": updated.id,
            "provider_thread_id": detail["thread"]["provider_thread_id"],
            "business_state": updated.business_state,
            "visible_labels": [label for label in updated.visible_labels.split(",") if label],
            "current_summary": updated.current_summary,
            "latest_confidence_band": updated.latest_confidence_band,
            "resurfacing_source": updated.resurfacing_source,
            "action_reason": updated.action_reason,
        },
    }


def list_thread_tasks(*, thread_id: int) -> list[dict]:
    return list_thread_scheduled_tasks(thread_id=thread_id, runtime=_runtime())


def create_thread_task(
    *,
    thread_id: int,
    task_type: str,
    due_at,
    created_by: str,
) -> dict:
    return asdict(
        create_thread_reminder(
            thread_id=thread_id,
            due_at=due_at,
            created_by=created_by,
            task_type=task_type,
            runtime=_runtime(),
        )
    )


def complete_task(*, thread_id: int, task_id: int) -> dict:
    return asdict(
        complete_thread_task(
            thread_id=thread_id,
            task_id=task_id,
            runtime=_runtime(),
        )
    )


def ingest_manual_email_messages(*, source_type: str, messages: list[Mapping[str, object]]) -> dict:
    report = pull_new_messages_report(manual_payload=[dict(item) for item in messages])
    normalized_messages = report.messages
    runtime = _runtime()
    graph = build_email_triage_graph()
    persisted = False
    processed_count = 0
    thread_ids: set[int] = set()

    def _execute() -> None:
        nonlocal persisted, processed_count
        for message in normalized_messages:
            result = run_email_triage_workflow(
                EmailMessage(
                    provider_message_id=message.provider_message_id,
                    provider_thread_id=message.provider_thread_id,
                    from_address=message.from_address,
                    subject=message.subject,
                    body_text=message.body_text,
                    received_at=message.received_at,
                    normalized_at=message.normalized_at,
                    source=message.source,
                ),
                graph=graph,
                runtime=runtime,
            )
            processed_count += 1
            if result.email_thread_id is not None:
                thread_ids.add(result.email_thread_id)
        persisted = True

    try:
        record_agent_run(
            agent_name="email_manual_ingest",
            source_type=source_type,
            source_id=f"count:{len(normalized_messages)}",
            execute=_execute,
        )
    except SQLAlchemyError:
        persisted = False

    return {
        "status": "accepted",
        "source_type": source_type,
        "message_count": len(normalized_messages),
        "persisted": persisted,
        "thread_count": len(thread_ids),
        "processed_count": processed_count,
        "failed_message_count": sum(report.failure_counts.values()),
        "normalization_failures": report.failure_counts,
    }


__all__ = [
    "get_thread_detail",
    "create_thread_task",
    "complete_task",
    "ingest_manual_email_messages",
    "list_drafts",
    "list_proposals",
    "list_thread_tasks",
    "list_threads",
    "override_thread",
    "reprocess_thread",
]
