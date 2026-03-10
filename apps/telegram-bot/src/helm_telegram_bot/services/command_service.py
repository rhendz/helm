from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from email_agent.adapters import build_helm_runtime
from email_agent.operator import (
    DraftTransitionResult,
    approve_draft,
    list_open_actions,
    list_pending_drafts,
    snooze_draft,
)
from email_agent.reminders import create_thread_reminder
from helm_observability.logging import get_logger

logger = get_logger("helm_telegram_bot.services.command_service")


@dataclass(frozen=True, slots=True)
class ThreadTaskTransitionResult:
    ok: bool
    message: str


class TelegramCommandService:
    def list_open_actions(self, *, limit: int = 5) -> list[object]:
        return list_open_actions(limit=limit, runtime=build_helm_runtime())

    def list_pending_drafts(self, *, limit: int = 5) -> list[object]:
        return list_pending_drafts(limit=limit, runtime=build_helm_runtime())

    def approve_draft(self, draft_id: int) -> DraftTransitionResult:
        result = approve_draft(draft_id, runtime=build_helm_runtime())
        if not result.ok:
            logger.warning("draft_transition_failed", action="approve", draft_id=draft_id)
        return result

    def snooze_draft(self, draft_id: int) -> DraftTransitionResult:
        result = snooze_draft(draft_id, runtime=build_helm_runtime())
        if not result.ok:
            logger.warning("draft_transition_failed", action="snooze", draft_id=draft_id)
        return result

    def create_thread_task(
        self,
        *,
        thread_id: int,
        due_at: datetime,
        task_type: str,
    ) -> ThreadTaskTransitionResult:
        result = create_thread_reminder(
            thread_id=thread_id,
            due_at=due_at,
            created_by="user",
            task_type=task_type,
            runtime=build_helm_runtime(),
        )
        if result.status != "accepted":
            logger.warning(
                "thread_task_create_failed",
                thread_id=thread_id,
                task_type=task_type,
                reason=result.reason,
            )
            return ThreadTaskTransitionResult(
                ok=False,
                message=f"Could not create {task_type} for thread {thread_id}.",
            )
        return ThreadTaskTransitionResult(
            ok=True,
            message=f"Created {task_type} task {result.task_id} for thread {thread_id}.",
        )
