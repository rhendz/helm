from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from email_agent.runtime import EmailAgentRuntime
from email_agent.thread_state import transition_for_scheduled_task


@dataclass(slots=True, frozen=True)
class ScheduledThreadTaskRunResult:
    processed_count: int
    skipped_count: int
    failed_count: int


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
    failed_count = 0
    for task in due_tasks:
        run = runtime.start_run(
            agent_name="email_scheduled_task",
            source_type="scheduled_thread_task",
            source_id=str(task.id),
        )
        try:
            thread = runtime.get_thread_by_id(task.email_thread_id)
            if thread is None:
                runtime.mark_run_failed(run.id, "thread_not_found")
                failed_count += 1
                continue

            thread_update = transition_for_scheduled_task(thread, task_type=task.task_type)
            runtime.update_thread_state(
                thread.id,
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
            runtime.mark_task_completed(task.id)
            runtime.mark_run_succeeded(run.id)
            processed_count += 1
        except Exception as exc:
            runtime.mark_run_failed(run.id, str(exc))
            failed_count += 1

    return ScheduledThreadTaskRunResult(
        processed_count=processed_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
    )
