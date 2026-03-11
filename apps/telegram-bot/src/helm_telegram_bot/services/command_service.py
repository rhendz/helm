from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from email_agent.operator import (
    DraftTransitionResult,
    DraftView,
    approve_draft,
    list_open_actions,
    list_pending_drafts,
    snooze_draft,
)
from email_agent.reminders import complete_scheduled_task, create_thread_reminder
from email_agent.reprocess import reprocess_email_thread
from email_agent.thread_state import transition_for_needs_review, transition_for_resolve
from helm_observability.logging import get_logger
from helm_runtime.email_agent import build_email_agent_runtime

logger = get_logger("helm_telegram_bot.services.command_service")


@dataclass(frozen=True, slots=True)
class ThreadTaskTransitionResult:
    ok: bool
    message: str


@dataclass(frozen=True, slots=True)
class ThreadOverrideTransitionResult:
    ok: bool
    message: str


@dataclass(frozen=True, slots=True)
class ThreadReprocessResult:
    ok: bool
    message: str


@dataclass(frozen=True, slots=True)
class ThreadDetailView:
    id: int
    business_state: str
    visible_labels: list[str]
    current_summary: str | None
    action_reason: str | None
    latest_confidence_band: str | None = None
    latest_message_from: str | None = None
    latest_message_subject: str | None = None
    latest_message_snippet: str | None = None
    latest_proposal_type: str | None = None
    latest_proposal_status: str | None = None
    latest_draft_approval_status: str | None = None
    latest_draft_preview: str | None = None
    pending_task_count: int = 0


@dataclass(frozen=True, slots=True)
class ThreadQueueView:
    id: int
    business_state: str
    current_summary: str | None


@dataclass(frozen=True, slots=True)
class ScheduledTaskView:
    id: int
    email_thread_id: int
    task_type: str
    due_at: datetime
    status: str
    reason: str | None


@dataclass(frozen=True, slots=True)
class ProposalView:
    id: int
    email_thread_id: int
    proposal_type: str
    status: str
    rationale: str | None


@dataclass(frozen=True, slots=True)
class DraftDetailView:
    id: int
    email_thread_id: int
    action_proposal_id: int | None
    status: str
    approval_status: str
    draft_subject: str | None
    draft_body: str
    transition_audits: list[dict]


class TelegramCommandService:
    def list_action_threads(self, *, limit: int = 5) -> list[ThreadQueueView]:
        items = build_email_agent_runtime().list_email_threads(label="Action", limit=limit)
        return [
            ThreadQueueView(
                id=item["id"],
                business_state=item["business_state"],
                current_summary=item.get("current_summary"),
            )
            for item in items
        ]

    def list_uninitialized_threads(self, *, limit: int = 5) -> list[ThreadQueueView]:
        items = build_email_agent_runtime().list_email_threads(
            business_state="uninitialized",
            limit=limit,
        )
        return [
            ThreadQueueView(
                id=item["id"],
                business_state=item["business_state"],
                current_summary=item.get("current_summary"),
            )
            for item in items
        ]

    def list_waiting_on_user_threads(self, *, limit: int = 5) -> list[ThreadQueueView]:
        items = build_email_agent_runtime().list_email_threads(
            business_state="waiting_on_user",
            limit=limit,
        )
        return [
            ThreadQueueView(
                id=item["id"],
                business_state=item["business_state"],
                current_summary=item.get("current_summary"),
            )
            for item in items
        ]

    def list_waiting_on_other_party_threads(self, *, limit: int = 5) -> list[ThreadQueueView]:
        items = build_email_agent_runtime().list_email_threads(
            business_state="waiting_on_other_party",
            limit=limit,
        )
        return [
            ThreadQueueView(
                id=item["id"],
                business_state=item["business_state"],
                current_summary=item.get("current_summary"),
            )
            for item in items
        ]

    def list_resolved_threads(self, *, limit: int = 5) -> list[ThreadQueueView]:
        items = build_email_agent_runtime().list_email_threads(
            business_state="resolved",
            limit=limit,
        )
        return [
            ThreadQueueView(
                id=item["id"],
                business_state=item["business_state"],
                current_summary=item.get("current_summary"),
            )
            for item in items
        ]

    def list_needs_review_threads(self, *, limit: int = 5) -> list[ThreadQueueView]:
        items = build_email_agent_runtime().list_email_threads(label="NeedsReview", limit=limit)
        return [
            ThreadQueueView(
                id=item["id"],
                business_state=item["business_state"],
                current_summary=item.get("current_summary"),
            )
            for item in items
        ]

    def list_threads(
        self,
        *,
        limit: int = 5,
        business_state: str | None = None,
        label: str | None = None,
    ) -> list[ThreadDetailView]:
        items = build_email_agent_runtime().list_email_threads(
            business_state=business_state,
            label=label,
            limit=limit,
        )
        return [
            ThreadDetailView(
                id=item["id"],
                business_state=item["business_state"],
                visible_labels=item.get("visible_labels", []),
                current_summary=item.get("current_summary"),
                action_reason=item.get("action_reason"),
            )
            for item in items
        ]

    def list_open_actions(self, *, limit: int = 5) -> list[object]:
        return list_open_actions(limit=limit, runtime=build_email_agent_runtime())

    def list_proposals(
        self,
        *,
        limit: int = 5,
        proposal_type: str | None = None,
    ) -> list[ProposalView]:
        items = build_email_agent_runtime().list_email_proposals(
            status="proposed",
            proposal_type=proposal_type,
            limit=limit,
        )
        return [
            ProposalView(
                id=item["id"],
                email_thread_id=item["email_thread_id"],
                proposal_type=item["proposal_type"],
                status=item["status"],
                rationale=item.get("rationale"),
            )
            for item in items
        ]

    def list_pending_drafts(
        self,
        *,
        limit: int = 5,
        approval_status: str | None = None,
    ) -> list[object]:
        if approval_status is None:
            return list_pending_drafts(limit=limit, runtime=build_email_agent_runtime())
        return [
            DraftView(
                id=item["id"],
                status=item["approval_status"],
                draft_text=item["preview"],
            )
            for item in build_email_agent_runtime().list_email_drafts(
                limit=limit,
                approval_status=approval_status,
            )
        ]

    def get_draft_detail(self, draft_id: int) -> DraftDetailView | None:
        runtime = build_email_agent_runtime()
        draft = runtime.get_email_draft_by_id(draft_id)
        if draft is None:
            return None
        audits = runtime.list_draft_transition_audits_for_draft(draft_id=draft_id)
        return DraftDetailView(
            id=draft["id"],
            email_thread_id=draft["email_thread_id"],
            action_proposal_id=draft.get("action_proposal_id"),
            status=draft["status"],
            approval_status=draft["approval_status"],
            draft_subject=draft.get("draft_subject"),
            draft_body=draft["draft_body"],
            transition_audits=audits,
        )

    def list_review_threads(self, *, limit: int = 5) -> list[ThreadDetailView]:
        return self.list_threads(
            business_state="needs_review",
            limit=limit,
        )

    def list_scheduled_tasks(
        self,
        *,
        limit: int = 5,
        status: str = "pending",
    ) -> list[ScheduledTaskView]:
        items = build_email_agent_runtime().list_scheduled_tasks(status=status, limit=limit)
        return [
            ScheduledTaskView(
                id=item["id"],
                email_thread_id=item["email_thread_id"],
                task_type=item["task_type"],
                due_at=item["due_at"],
                status=item["status"],
                reason=item.get("reason"),
            )
            for item in items
        ]

    def get_thread_detail(self, thread_id: int) -> ThreadDetailView | None:
        runtime = build_email_agent_runtime()
        detail = runtime.get_email_thread_detail(thread_id=thread_id)
        if detail is None:
            return None
        thread = detail["thread"]
        proposals = detail.get("proposals", [])
        drafts = detail.get("drafts", [])
        messages = detail.get("messages", [])
        tasks = runtime.list_scheduled_tasks_for_thread(thread_id=thread_id)
        latest_proposal = proposals[0] if proposals else None
        latest_draft = drafts[0] if drafts else None
        latest_message = messages[0] if messages else None
        return ThreadDetailView(
            id=thread["id"],
            business_state=thread["business_state"],
            visible_labels=thread["visible_labels"],
            current_summary=thread["current_summary"],
            action_reason=thread["action_reason"],
            latest_confidence_band=thread.get("latest_confidence_band"),
            latest_message_from=(
                latest_message.get("from_address") if latest_message is not None else None
            ),
            latest_message_subject=(
                latest_message.get("subject") if latest_message is not None else None
            ),
            latest_message_snippet=(
                latest_message.get("snippet") if latest_message is not None else None
            ),
            latest_proposal_type=(
                latest_proposal.get("proposal_type") if latest_proposal is not None else None
            ),
            latest_proposal_status=(
                latest_proposal.get("status") if latest_proposal is not None else None
            ),
            latest_draft_approval_status=(
                latest_draft.get("approval_status") if latest_draft is not None else None
            ),
            latest_draft_preview=latest_draft.get("preview") if latest_draft is not None else None,
            pending_task_count=sum(1 for task in tasks if task.get("status") == "pending"),
        )

    def approve_draft(self, draft_id: int) -> DraftTransitionResult:
        result = approve_draft(draft_id, runtime=build_email_agent_runtime())
        if not result.ok:
            logger.warning("draft_transition_failed", action="approve", draft_id=draft_id)
        return result

    def snooze_draft(self, draft_id: int) -> DraftTransitionResult:
        result = snooze_draft(draft_id, runtime=build_email_agent_runtime())
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
            runtime=build_email_agent_runtime(),
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

    def complete_task(self, task_id: int) -> ThreadTaskTransitionResult:
        result = complete_scheduled_task(task_id=task_id, runtime=build_email_agent_runtime())
        if result.status != "accepted":
            logger.warning(
                "thread_task_complete_failed",
                task_id=task_id,
                reason=result.reason,
            )
            return ThreadTaskTransitionResult(
                ok=False,
                message=f"Could not complete task {task_id}.",
            )
        return ThreadTaskTransitionResult(
            ok=True,
            message=f"Completed task {task_id} for thread {result.thread_id}.",
        )

    def resolve_thread(self, thread_id: int) -> ThreadOverrideTransitionResult:
        runtime = build_email_agent_runtime()
        thread = runtime.get_thread_by_id(thread_id)
        if thread is None:
            return ThreadOverrideTransitionResult(
                ok=False,
                message=f"Thread {thread_id} not found.",
            )
        thread_update = transition_for_resolve(thread)
        updated = runtime.update_thread_state(
            thread_id,
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
        if updated is None:
            return ThreadOverrideTransitionResult(
                ok=False,
                message=f"Thread {thread_id} not found.",
            )
        return ThreadOverrideTransitionResult(
            ok=True,
            message=f"Marked thread {thread_id} resolved.",
        )

    def mark_thread_needs_review(self, thread_id: int) -> ThreadOverrideTransitionResult:
        runtime = build_email_agent_runtime()
        thread = runtime.get_thread_by_id(thread_id)
        if thread is None:
            return ThreadOverrideTransitionResult(
                ok=False,
                message=f"Thread {thread_id} not found.",
            )
        thread_update = transition_for_needs_review(thread)
        updated = runtime.update_thread_state(
            thread_id,
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
        if updated is None:
            return ThreadOverrideTransitionResult(
                ok=False,
                message=f"Thread {thread_id} not found.",
            )
        return ThreadOverrideTransitionResult(
            ok=True,
            message=f"Marked thread {thread_id} for review.",
        )

    def reprocess_thread(self, thread_id: int, *, dry_run: bool = True) -> ThreadReprocessResult:
        result = reprocess_email_thread(
            thread_id=thread_id,
            dry_run=dry_run,
            runtime=build_email_agent_runtime(),
        )
        if result.status != "accepted":
            return ThreadReprocessResult(
                ok=False,
                message=f"Could not reprocess thread {thread_id}: {result.reason}.",
            )
        mode = "dry-run" if dry_run else "executed"
        return ThreadReprocessResult(
            ok=True,
            message=f"Reprocess {mode} for thread {thread_id}: {result.workflow_status}.",
        )
