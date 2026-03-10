from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from email_agent.runtime import EmailAgentRuntime


@dataclass(slots=True, frozen=True)
class ScheduledThreadTaskRunResult:
    processed_count: int
    skipped_count: int


def run_due_scheduled_thread_tasks(
    *,
    runtime: EmailAgentRuntime,
    now: datetime | None = None,
    limit: int = 100,
) -> ScheduledThreadTaskRunResult:
    due_before = now or datetime.now(tz=UTC)
    due_tasks = runtime.list_due_tasks(due_before=due_before, limit=limit)

    processed_count = 0
    skipped_count = 0
    for task in due_tasks:
        thread = runtime.get_thread_by_id(task.email_thread_id)
        if thread is None:
            skipped_count += 1
            continue

        visible_labels = _merge_action_label(thread.visible_labels)
        resurfacing_source, action_reason = _derive_task_metadata(task.task_type)
        runtime.update_thread_state(
            thread.id,
            business_state=thread.business_state,
            visible_labels=visible_labels,
            latest_confidence_band=thread.latest_confidence_band,
            resurfacing_source=resurfacing_source,
            action_reason=action_reason,
            current_summary=thread.current_summary,
            last_message_id=thread.last_message_id,
            last_inbound_message_id=thread.last_inbound_message_id,
            last_outbound_message_id=thread.last_outbound_message_id,
        )
        runtime.mark_task_completed(task.id)
        processed_count += 1

    return ScheduledThreadTaskRunResult(
        processed_count=processed_count,
        skipped_count=skipped_count,
    )


def _derive_task_metadata(task_type: str) -> tuple[str, str]:
    if task_type == "followup":
        return "stale_followup", "followup_due"
    return "reminder_due", "reminder_due"


def _merge_action_label(serialized_labels: str) -> tuple[str, ...]:
    labels = [label for label in serialized_labels.split(",") if label]
    labels.append("Action")
    return tuple(sorted(set(labels)))
