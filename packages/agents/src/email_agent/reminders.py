from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError

from email_agent.runtime import EmailAgentRuntime


@dataclass(frozen=True, slots=True)
class ScheduledTaskCreateResult:
    status: str
    thread_id: int
    task_id: int | None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ScheduledTaskCompleteResult:
    status: str
    thread_id: int
    task_id: int
    completed: bool
    reason: str | None = None


def list_thread_scheduled_tasks(
    *,
    thread_id: int,
    runtime: EmailAgentRuntime,
) -> list[dict]:
    try:
        return runtime.list_scheduled_tasks_for_thread(thread_id=thread_id)
    except SQLAlchemyError:
        return []


def create_thread_reminder(
    *,
    thread_id: int,
    due_at: datetime,
    created_by: str,
    task_type: str,
    runtime: EmailAgentRuntime,
) -> ScheduledTaskCreateResult:
    try:
        thread = runtime.get_thread_by_id(thread_id)
        if thread is None:
            return ScheduledTaskCreateResult(
                status="not_found",
                thread_id=thread_id,
                task_id=None,
                reason="thread_not_found",
            )

        task = runtime.create_scheduled_task(
            thread_id=thread_id,
            task_type=task_type,
            created_by=created_by,
            due_at=due_at,
            reason=_task_reason(task_type),
        )
    except SQLAlchemyError:
        return ScheduledTaskCreateResult(
            status="unavailable",
            thread_id=thread_id,
            task_id=None,
            reason="storage_unavailable",
        )

    return ScheduledTaskCreateResult(
        status="accepted",
        thread_id=thread_id,
        task_id=task["id"],
    )


def complete_thread_task(
    *,
    thread_id: int,
    task_id: int,
    runtime: EmailAgentRuntime,
) -> ScheduledTaskCompleteResult:
    try:
        tasks = runtime.list_scheduled_tasks_for_thread(thread_id=thread_id)
        matching = next((task for task in tasks if task["id"] == task_id), None)
        if matching is None:
            return ScheduledTaskCompleteResult(
                status="not_found",
                thread_id=thread_id,
                task_id=task_id,
                completed=False,
                reason="task_not_found",
            )
        completed = runtime.mark_task_completed(task_id)
    except SQLAlchemyError:
        return ScheduledTaskCompleteResult(
            status="unavailable",
            thread_id=thread_id,
            task_id=task_id,
            completed=False,
            reason="storage_unavailable",
        )

    return ScheduledTaskCompleteResult(
        status="accepted" if completed else "not_found",
        thread_id=thread_id,
        task_id=task_id,
        completed=completed,
        reason=None if completed else "task_not_found",
    )


def _task_reason(task_type: str) -> str:
    if task_type == "followup":
        return "followup_due"
    return "reminder_due"
