from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from helm_storage.db import SessionLocal
from helm_storage.repositories.action_proposals import SQLAlchemyActionProposalRepository
from helm_storage.repositories.agent_runs import SQLAlchemyAgentRunRepository
from helm_storage.repositories.contracts import (
    NewActionProposal,
    NewDigestItem,
    NewEmailDraft,
    NewEmailThread,
    NewScheduledThreadTask,
)
from helm_storage.repositories.digest_items import SQLAlchemyDigestItemRepository
from helm_storage.repositories.email_drafts import SQLAlchemyEmailDraftRepository
from helm_storage.repositories.email_messages import SQLAlchemyEmailMessageRepository
from helm_storage.repositories.email_threads import SQLAlchemyEmailThreadRepository
from helm_storage.repositories.scheduled_thread_tasks import SQLAlchemyScheduledThreadTaskRepository
from sqlalchemy.orm import Session

from email_agent.runtime import (
    DigestRecord,
    DraftRecord,
    EmailAgentRuntime,
    MessageRecord,
    ProposalRecord,
    RunRecord,
    ScheduledTaskRecord,
    ThreadRecord,
)


class HelmEmailAgentRuntime(EmailAgentRuntime):
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def start_run(self, *, agent_name: str, source_type: str, source_id: str | None) -> RunRecord:
        with self.session_factory() as session:
            record = SQLAlchemyAgentRunRepository(session).start_run(
                agent_name=agent_name,
                source_type=source_type,
                source_id=source_id,
            )
            return RunRecord(id=record.id)

    def mark_run_succeeded(self, run_id: int) -> None:
        with self.session_factory() as session:
            SQLAlchemyAgentRunRepository(session).mark_succeeded(run_id)

    def mark_run_failed(self, run_id: int, error_message: str) -> None:
        with self.session_factory() as session:
            SQLAlchemyAgentRunRepository(session).mark_failed(run_id, error_message)

    def get_or_create_thread(self, *, provider_thread_id: str) -> ThreadRecord:
        with self.session_factory() as session:
            record = SQLAlchemyEmailThreadRepository(session).get_or_create(
                NewEmailThread(provider_thread_id=provider_thread_id)
            )
            return _thread_record(record)

    def get_thread_by_id(self, thread_id: int) -> ThreadRecord | None:
        with self.session_factory() as session:
            record = SQLAlchemyEmailThreadRepository(session).get_by_id(thread_id)
            return _thread_record(record) if record is not None else None

    def get_thread_by_provider_thread_id(self, provider_thread_id: str) -> ThreadRecord | None:
        with self.session_factory() as session:
            record = SQLAlchemyEmailThreadRepository(session).get_by_provider_thread_id(
                provider_thread_id,
            )
            return _thread_record(record) if record is not None else None

    def upsert_inbound_message(
        self,
        *,
        message: object,
        email_thread_id: int,
    ) -> MessageRecord:
        with self.session_factory() as session:
            record = SQLAlchemyEmailMessageRepository(session).upsert_from_normalized(
                message,
                email_thread_id=email_thread_id,
                direction="inbound",
            )
            return MessageRecord(id=record.id)

    def mark_message_processed(self, provider_message_id: str, *, processed_at: datetime) -> None:
        with self.session_factory() as session:
            SQLAlchemyEmailMessageRepository(session).mark_processed(
                provider_message_id,
                processed_at=processed_at,
            )

    def update_thread_state(
        self,
        thread_id: int,
        *,
        business_state: str,
        visible_labels: tuple[str, ...],
        latest_confidence_band: str | None,
        resurfacing_source: str | None,
        action_reason: str | None,
        current_summary: str | None,
        last_message_id: int | None = None,
        last_inbound_message_id: int | None = None,
        last_outbound_message_id: int | None = None,
    ) -> ThreadRecord | None:
        with self.session_factory() as session:
            record = SQLAlchemyEmailThreadRepository(session).update_state(
                thread_id,
                business_state=business_state,
                visible_labels=visible_labels,
                latest_confidence_band=latest_confidence_band,
                resurfacing_source=resurfacing_source,
                action_reason=action_reason,
                current_summary=current_summary,
                last_message_id=last_message_id,
                last_inbound_message_id=last_inbound_message_id,
                last_outbound_message_id=last_outbound_message_id,
            )
            return _thread_record(record) if record is not None else None

    def get_latest_proposal_for_thread(self, *, email_thread_id: int) -> ProposalRecord | None:
        with self.session_factory() as session:
            record = SQLAlchemyActionProposalRepository(session).get_latest_for_thread(
                email_thread_id=email_thread_id,
            )
            return ProposalRecord(id=record.id) if record is not None else None

    def create_proposal(
        self,
        *,
        email_thread_id: int,
        proposal_type: str,
        rationale: str | None,
        confidence_band: str | None,
    ) -> ProposalRecord:
        with self.session_factory() as session:
            record = SQLAlchemyActionProposalRepository(session).create(
                NewActionProposal(
                    email_thread_id=email_thread_id,
                    proposal_type=proposal_type,
                    rationale=rationale,
                    confidence_band=confidence_band,
                )
            )
            return ProposalRecord(id=record.id)

    def get_latest_email_draft_for_thread(self, *, email_thread_id: int) -> DraftRecord | None:
        with self.session_factory() as session:
            record = SQLAlchemyEmailDraftRepository(session).get_latest_for_thread(
                email_thread_id=email_thread_id,
            )
            return DraftRecord(id=record.id) if record is not None else None

    def create_email_draft(
        self,
        *,
        email_thread_id: int,
        action_proposal_id: int | None,
        draft_body: str,
        draft_subject: str | None,
    ) -> DraftRecord:
        with self.session_factory() as session:
            record = SQLAlchemyEmailDraftRepository(session).create(
                NewEmailDraft(
                    email_thread_id=email_thread_id,
                    action_proposal_id=action_proposal_id,
                    draft_body=draft_body,
                    draft_subject=draft_subject,
                    status="generated",
                    approval_status="pending_user",
                )
            )
            return DraftRecord(id=record.id)

    def get_email_draft_by_id(self, draft_id: int) -> dict | None:
        with self.session_factory() as session:
            record = SQLAlchemyEmailDraftRepository(session).get_by_id(draft_id)
            if record is None:
                return None
            return {
                "id": record.id,
                "email_thread_id": record.email_thread_id,
                "action_proposal_id": record.action_proposal_id,
                "status": record.status,
                "approval_status": record.approval_status,
                "draft_body": record.draft_body,
                "draft_subject": record.draft_subject,
            }

    def set_email_draft_approval_status(self, draft_id: int, *, approval_status: str) -> bool:
        with self.session_factory() as session:
            return SQLAlchemyEmailDraftRepository(session).set_approval_status(
                draft_id,
                approval_status=approval_status,
            )

    def find_matching_digest(
        self,
        *,
        domain: str,
        title: str,
        summary: str,
    ) -> DigestRecord | None:
        with self.session_factory() as session:
            record = SQLAlchemyDigestItemRepository(session).find_matching(
                domain=domain,
                title=title,
                summary=summary,
                related_action_id=None,
            )
            return DigestRecord(id=record.id) if record is not None else None

    def create_digest(
        self,
        *,
        domain: str,
        title: str,
        summary: str,
        priority: int,
    ) -> DigestRecord:
        with self.session_factory() as session:
            record = SQLAlchemyDigestItemRepository(session).create(
                NewDigestItem(
                    domain=domain,
                    title=title,
                    summary=summary,
                    priority=priority,
                )
            )
            return DigestRecord(id=record.id)

    def list_due_tasks(
        self,
        *,
        due_before: datetime,
        limit: int = 100,
    ) -> list[ScheduledTaskRecord]:
        with self.session_factory() as session:
            records = SQLAlchemyScheduledThreadTaskRepository(session).list_due(
                due_before=due_before,
                limit=limit,
            )
            return [
                ScheduledTaskRecord(
                    id=record.id,
                    email_thread_id=record.email_thread_id,
                    task_type=record.task_type,
                )
                for record in records
            ]

    def mark_task_completed(self, task_id: int) -> bool:
        with self.session_factory() as session:
            return SQLAlchemyScheduledThreadTaskRepository(session).mark_completed(task_id)

    def list_email_threads(self, *, limit: int = 20) -> list[dict]:
        with self.session_factory() as session:
            records = SQLAlchemyEmailThreadRepository(session).list_recent(limit=limit)
            return [
                {
                    "id": thread.id,
                    "provider_thread_id": thread.provider_thread_id,
                    "business_state": thread.business_state,
                    "visible_labels": _split_labels(thread.visible_labels),
                    "current_summary": thread.current_summary,
                    "latest_confidence_band": thread.latest_confidence_band,
                    "resurfacing_source": thread.resurfacing_source,
                    "action_reason": thread.action_reason,
                }
                for thread in records
            ]

    def list_email_proposals(self, *, limit: int = 20) -> list[dict]:
        with self.session_factory() as session:
            records = SQLAlchemyActionProposalRepository(session).list_recent(limit=limit)
            return [
                {
                    "id": proposal.id,
                    "email_thread_id": proposal.email_thread_id,
                    "proposal_type": proposal.proposal_type,
                    "status": proposal.status,
                    "confidence_band": proposal.confidence_band,
                    "rationale": proposal.rationale,
                }
                for proposal in records
            ]

    def list_email_drafts(self, *, limit: int = 20) -> list[dict]:
        with self.session_factory() as session:
            records = SQLAlchemyEmailDraftRepository(session).list_recent(limit=limit)
            return [
                {
                    "id": draft.id,
                    "email_thread_id": draft.email_thread_id,
                    "action_proposal_id": draft.action_proposal_id,
                    "status": draft.status,
                    "approval_status": draft.approval_status,
                    "preview": draft.draft_body[:120],
                    "draft_subject": draft.draft_subject,
                }
                for draft in records
            ]

    def get_email_thread_detail(self, *, thread_id: int) -> dict | None:
        with self.session_factory() as session:
            thread = SQLAlchemyEmailThreadRepository(session).get_by_id(thread_id)
            if thread is None:
                return None

            proposals = SQLAlchemyActionProposalRepository(session).list_for_thread(
                email_thread_id=thread_id,
            )
            drafts = SQLAlchemyEmailDraftRepository(session).list_for_thread(
                email_thread_id=thread_id,
            )
            messages = SQLAlchemyEmailMessageRepository(session).list_for_thread(
                email_thread_id=thread_id,
            )

            return {
                "thread": {
                    "id": thread.id,
                    "provider_thread_id": thread.provider_thread_id,
                    "business_state": thread.business_state,
                    "visible_labels": _split_labels(thread.visible_labels),
                    "current_summary": thread.current_summary,
                    "latest_confidence_band": thread.latest_confidence_band,
                    "resurfacing_source": thread.resurfacing_source,
                    "action_reason": thread.action_reason,
                },
                "proposals": [
                    {
                        "id": proposal.id,
                        "email_thread_id": proposal.email_thread_id,
                        "proposal_type": proposal.proposal_type,
                        "status": proposal.status,
                        "confidence_band": proposal.confidence_band,
                        "rationale": proposal.rationale,
                    }
                    for proposal in proposals
                ],
                "drafts": [
                    {
                        "id": draft.id,
                        "email_thread_id": draft.email_thread_id,
                        "action_proposal_id": draft.action_proposal_id,
                        "status": draft.status,
                        "approval_status": draft.approval_status,
                        "preview": draft.draft_body[:120],
                        "draft_subject": draft.draft_subject,
                    }
                    for draft in drafts
                ],
                "messages": [
                    {
                        "id": message.id,
                        "provider_message_id": message.provider_message_id,
                        "provider_thread_id": message.provider_thread_id,
                        "direction": message.direction,
                        "from_address": message.from_address,
                        "subject": message.subject,
                        "snippet": message.snippet,
                        "received_at": message.received_at,
                        "processed_at": message.processed_at,
                        "source": message.source,
                    }
                    for message in messages
                ],
            }

    def get_latest_inbound_email_message(self, *, thread_id: int) -> dict | None:
        with self.session_factory() as session:
            record = SQLAlchemyEmailMessageRepository(session).get_latest_inbound_for_thread(
                email_thread_id=thread_id,
            )
            if record is None:
                return None
            return {
                "provider_message_id": record.provider_message_id,
                "provider_thread_id": record.provider_thread_id,
                "from_address": record.from_address,
                "subject": record.subject,
                "body_text": record.body_text,
                "received_at": record.received_at,
                "normalized_at": record.normalized_at,
                "source": record.source,
            }

    def list_scheduled_tasks_for_thread(self, *, thread_id: int) -> list[dict]:
        with self.session_factory() as session:
            records = SQLAlchemyScheduledThreadTaskRepository(session).list_for_thread(
                email_thread_id=thread_id,
            )
            return [
                {
                    "id": record.id,
                    "email_thread_id": record.email_thread_id,
                    "task_type": record.task_type,
                    "created_by": record.created_by,
                    "due_at": record.due_at,
                    "status": record.status,
                    "reason": record.reason,
                }
                for record in records
            ]

    def create_scheduled_task(
        self,
        *,
        thread_id: int,
        task_type: str,
        created_by: str,
        due_at: datetime,
        reason: str | None,
    ) -> dict:
        with self.session_factory() as session:
            record = SQLAlchemyScheduledThreadTaskRepository(session).create(
                NewScheduledThreadTask(
                    email_thread_id=thread_id,
                    task_type=task_type,
                    created_by=created_by,
                    due_at=due_at,
                    reason=reason,
                )
            )
            return {
                "id": record.id,
                "email_thread_id": record.email_thread_id,
                "task_type": record.task_type,
                "created_by": record.created_by,
                "due_at": record.due_at,
                "status": record.status,
                "reason": record.reason,
            }


def build_helm_runtime(
    session_factory: Callable[[], Session] | None = None,
) -> EmailAgentRuntime:
    return HelmEmailAgentRuntime(session_factory=session_factory or SessionLocal)


def _thread_record(record: object) -> ThreadRecord:
    return ThreadRecord(
        id=record.id,
        business_state=record.business_state,
        visible_labels=record.visible_labels,
        current_summary=record.current_summary,
        latest_confidence_band=record.latest_confidence_band,
        resurfacing_source=record.resurfacing_source,
        action_reason=record.action_reason,
        last_message_id=record.last_message_id,
        last_inbound_message_id=record.last_inbound_message_id,
        last_outbound_message_id=record.last_outbound_message_id,
    )


def _split_labels(value: str) -> list[str]:
    if not value:
        return []
    return [label for label in value.split(",") if label]
