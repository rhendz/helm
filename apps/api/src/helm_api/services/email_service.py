from dataclasses import asdict

from email_agent.adapters import build_helm_runtime
from email_agent.query import (
    get_email_thread_detail,
    list_email_drafts,
    list_email_proposals,
    list_email_threads,
)
from email_agent.reminders import create_thread_reminder, list_thread_scheduled_tasks
from email_agent.reprocess import reprocess_email_thread


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


__all__ = [
    "get_thread_detail",
    "create_thread_task",
    "list_drafts",
    "list_proposals",
    "list_thread_tasks",
    "list_threads",
    "reprocess_thread",
]
