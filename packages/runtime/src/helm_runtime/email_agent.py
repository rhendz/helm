from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from email_agent.runtime import (
    ClassificationArtifactRecord,
    DeepSeedQueueRecord,
    DigestRecord,
    DraftRecord,
    EmailAgentRuntime,
    MessageRecord,
    ProposalRecord,
    RunRecord,
    ScheduledTaskRecord,
    SendAttemptRecord,
    ThreadRecord,
)
from helm_storage.db import SessionLocal
from helm_storage.repositories.action_proposals import SQLAlchemyActionProposalRepository
from helm_storage.repositories.agent_runs import SQLAlchemyAgentRunRepository
from helm_storage.repositories.classification_artifacts import (
    SQLAlchemyClassificationArtifactRepository,
)
from helm_storage.repositories.contracts import (
    EmailDraftContentPatch,
    EmailSendAttemptPatch,
    NewActionProposal,
    NewClassificationArtifact,
    NewDigestItem,
    NewDraftReasoningArtifact,
    NewEmailDeepSeedQueueItem,
    NewEmailDraft,
    NewEmailSendAttempt,
    NewEmailThread,
    NewOutboundEmailMessage,
    NewScheduledThreadTask,
)
from helm_storage.repositories.digest_items import SQLAlchemyDigestItemRepository
from helm_storage.repositories.draft_reasoning_artifacts import (
    SQLAlchemyDraftReasoningArtifactRepository,
)
from helm_storage.repositories.draft_transition_audits import (
    SQLAlchemyDraftTransitionAuditRepository,
)
from helm_storage.repositories.email_deep_seed_queue import SQLAlchemyEmailDeepSeedQueueRepository
from helm_storage.repositories.email_drafts import SQLAlchemyEmailDraftRepository
from helm_storage.repositories.email_messages import SQLAlchemyEmailMessageRepository
from helm_storage.repositories.email_send_attempts import SQLAlchemyEmailSendAttemptRepository
from helm_storage.repositories.email_threads import SQLAlchemyEmailThreadRepository
from helm_storage.repositories.scheduled_thread_tasks import SQLAlchemyScheduledThreadTaskRepository
from sqlalchemy.orm import Session


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

    def create_classification_artifact(
        self,
        *,
        email_thread_id: int,
        email_message_id: int,
        classification: str,
        priority_score: int,
        business_state: str,
        visible_labels: tuple[str, ...],
        action_reason: str | None,
        resurfacing_source: str | None,
        confidence_band: str | None,
        decision_context: dict[str, object],
        model_name: str | None = None,
        prompt_version: str | None = None,
    ) -> ClassificationArtifactRecord:
        with self.session_factory() as session:
            record = SQLAlchemyClassificationArtifactRepository(session).create(
                NewClassificationArtifact(
                    email_thread_id=email_thread_id,
                    email_message_id=email_message_id,
                    classification=classification,
                    priority_score=priority_score,
                    business_state=business_state,
                    visible_labels=visible_labels,
                    action_reason=action_reason,
                    resurfacing_source=resurfacing_source,
                    confidence_band=confidence_band,
                    decision_context=decision_context,
                    model_name=model_name,
                    prompt_version=prompt_version,
                )
            )
            return ClassificationArtifactRecord(id=record.id)

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
        reasoning_artifact: dict[str, object] | None = None,
    ) -> DraftRecord:
        with self.session_factory() as session:
            draft_repository = SQLAlchemyEmailDraftRepository(session)
            record = draft_repository.create(
                NewEmailDraft(
                    email_thread_id=email_thread_id,
                    action_proposal_id=action_proposal_id,
                    draft_body=draft_body,
                    draft_subject=draft_subject,
                    status="generated",
                    approval_status="pending_user",
                )
            )
            if reasoning_artifact is not None:
                artifact_record = _create_draft_reasoning_artifact(
                    session=session,
                    draft_id=record.id,
                    email_thread_id=email_thread_id,
                    action_proposal_id=action_proposal_id,
                    reasoning_artifact=reasoning_artifact,
                )
                draft_repository.set_reasoning_artifact_ref(
                    record.id,
                    artifact_ref=artifact_record.internal_uuid,
                )
            return DraftRecord(id=record.id)

    def update_email_draft(
        self,
        *,
        draft_id: int,
        email_thread_id: int,
        action_proposal_id: int | None,
        draft_body: str,
        draft_subject: str | None,
        reasoning_artifact: dict[str, object] | None = None,
    ) -> DraftRecord | None:
        with self.session_factory() as session:
            draft_repository = SQLAlchemyEmailDraftRepository(session)
            existing = draft_repository.get_by_id(draft_id)
            if existing is None:
                return None

            approval_status = existing.approval_status
            if draft_body != existing.draft_body or draft_subject != existing.draft_subject:
                approval_status = "pending_user"

            artifact_ref = existing.draft_reasoning_artifact_ref
            if reasoning_artifact is not None:
                artifact_record = _create_draft_reasoning_artifact(
                    session=session,
                    draft_id=draft_id,
                    email_thread_id=email_thread_id,
                    action_proposal_id=action_proposal_id,
                    reasoning_artifact=reasoning_artifact,
                )
                artifact_ref = artifact_record.internal_uuid

            updated = draft_repository.update_content(
                draft_id,
                EmailDraftContentPatch(
                    draft_body=draft_body,
                    draft_subject=draft_subject,
                    action_proposal_id=action_proposal_id,
                    status="generated",
                    approval_status=approval_status,
                    draft_reasoning_artifact_ref=artifact_ref,
                ),
            )
            return DraftRecord(id=updated.id) if updated is not None else None

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
                "draft_reasoning_artifact_ref": record.draft_reasoning_artifact_ref,
                "final_sent_message_id": record.final_sent_message_id,
            }

    def list_draft_reasoning_artifacts_for_draft(self, *, draft_id: int) -> list[dict]:
        with self.session_factory() as session:
            records = SQLAlchemyDraftReasoningArtifactRepository(session).list_for_draft(
                email_draft_id=draft_id,
            )
            return [_draft_reasoning_artifact_payload(record) for record in records]

    def list_draft_transition_audits_for_draft(self, *, draft_id: int) -> list[dict]:
        with self.session_factory() as session:
            records = SQLAlchemyDraftTransitionAuditRepository(session).list_for_draft(
                draft_id=draft_id,
            )
            return [
                {
                    "id": row.id,
                    "draft_id": row.draft_id,
                    "action": row.action,
                    "from_status": row.from_status,
                    "to_status": row.to_status,
                    "success": row.success,
                    "reason": row.reason,
                    "created_at": row.created_at,
                }
                for row in records
            ]

    def list_send_attempts_for_draft(self, *, draft_id: int) -> list[dict]:
        with self.session_factory() as session:
            records = SQLAlchemyEmailSendAttemptRepository(session).list_for_draft(
                draft_id=draft_id,
            )
            return [
                {
                    "id": row.id,
                    "draft_id": row.draft_id,
                    "email_thread_id": row.email_thread_id,
                    "attempt_number": row.attempt_number,
                    "status": row.status,
                    "failure_class": row.failure_class,
                    "failure_message": row.failure_message,
                    "provider_error_code": row.provider_error_code,
                    "provider_message_id": row.provider_message_id,
                    "started_at": row.started_at,
                    "completed_at": row.completed_at,
                }
                for row in records
            ]

    def set_email_draft_approval_status(self, draft_id: int, *, approval_status: str) -> bool:
        with self.session_factory() as session:
            return SQLAlchemyEmailDraftRepository(session).set_approval_status(
                draft_id,
                approval_status=approval_status,
            )

    def set_email_draft_status(self, draft_id: int, *, status: str) -> bool:
        with self.session_factory() as session:
            return SQLAlchemyEmailDraftRepository(session).set_status(
                draft_id,
                status=status,
            )

    def set_email_draft_final_sent_message(self, draft_id: int, *, message_id: int) -> bool:
        with self.session_factory() as session:
            return SQLAlchemyEmailDraftRepository(session).set_final_sent_message(
                draft_id,
                message_id=message_id,
            )

    def create_draft_transition_audit(
        self,
        *,
        draft_id: int,
        action: str,
        from_status: str | None,
        to_status: str | None,
        success: bool,
        reason: str | None,
    ) -> None:
        with self.session_factory() as session:
            SQLAlchemyDraftTransitionAuditRepository(session).create(
                draft_id=draft_id,
                action=action,
                from_status=from_status,
                to_status=to_status,
                success=success,
                reason=reason,
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

    def get_send_attempt_count_for_draft(self, *, draft_id: int) -> int:
        with self.session_factory() as session:
            return SQLAlchemyEmailSendAttemptRepository(session).count_for_draft(draft_id=draft_id)

    def has_successful_send_for_draft(self, *, draft_id: int) -> bool:
        with self.session_factory() as session:
            return (
                SQLAlchemyEmailSendAttemptRepository(session).get_success_for_draft(
                    draft_id=draft_id,
                )
                is not None
            )

    def create_send_attempt(
        self,
        *,
        draft_id: int,
        email_thread_id: int,
        attempt_number: int,
        started_at: datetime,
    ) -> SendAttemptRecord:
        with self.session_factory() as session:
            record = SQLAlchemyEmailSendAttemptRepository(session).create(
                NewEmailSendAttempt(
                    draft_id=draft_id,
                    email_thread_id=email_thread_id,
                    attempt_number=attempt_number,
                    started_at=started_at,
                )
            )
            return SendAttemptRecord(id=record.id)

    def complete_send_attempt(
        self,
        *,
        attempt_id: int,
        status: str,
        completed_at: datetime,
        failure_class: str | None = None,
        failure_message: str | None = None,
        provider_error_code: str | None = None,
        provider_message_id: str | None = None,
    ) -> SendAttemptRecord | None:
        with self.session_factory() as session:
            record = SQLAlchemyEmailSendAttemptRepository(session).update(
                attempt_id,
                EmailSendAttemptPatch(
                    status=status,
                    completed_at=completed_at,
                    failure_class=failure_class,
                    failure_message=failure_message,
                    provider_error_code=provider_error_code,
                    provider_message_id=provider_message_id,
                ),
            )
            return SendAttemptRecord(id=record.id) if record is not None else None

    def enqueue_deep_seed_thread(
        self,
        *,
        source_type: str,
        provider_thread_id: str,
        seed_reason: str,
        message_count: int,
        latest_received_at: datetime,
        sample_subject: str,
        from_addresses: tuple[str, ...],
        thread_payload: list[dict[str, object]],
    ) -> tuple[DeepSeedQueueRecord, bool]:
        with self.session_factory() as session:
            record, created = SQLAlchemyEmailDeepSeedQueueRepository(session).enqueue(
                NewEmailDeepSeedQueueItem(
                    source_type=source_type,
                    provider_thread_id=provider_thread_id,
                    seed_reason=seed_reason,
                    message_count=message_count,
                    latest_received_at=latest_received_at,
                    sample_subject=sample_subject,
                    from_addresses=from_addresses,
                    thread_payload=thread_payload,
                )
            )
            return DeepSeedQueueRecord(id=record.id), created

    def list_deep_seed_queue(
        self,
        *,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        with self.session_factory() as session:
            records = SQLAlchemyEmailDeepSeedQueueRepository(session).list_recent(
                status=status,
                limit=limit,
            )
            return [_deep_seed_queue_payload(record) for record in records]

    def mark_deep_seed_item_processing(self, item_id: int) -> dict | None:
        with self.session_factory() as session:
            record = SQLAlchemyEmailDeepSeedQueueRepository(session).mark_processing(item_id)
            return _deep_seed_queue_payload(record) if record is not None else None

    def mark_deep_seed_item_completed(
        self,
        item_id: int,
        *,
        email_thread_id: int | None,
        completed_at: datetime,
    ) -> dict | None:
        with self.session_factory() as session:
            record = SQLAlchemyEmailDeepSeedQueueRepository(session).mark_completed(
                item_id,
                email_thread_id=email_thread_id,
                completed_at=completed_at,
            )
            return _deep_seed_queue_payload(record) if record is not None else None

    def mark_deep_seed_item_failed(self, item_id: int, *, error_message: str) -> dict | None:
        with self.session_factory() as session:
            record = SQLAlchemyEmailDeepSeedQueueRepository(session).mark_failed(
                item_id,
                error_message=error_message,
            )
            return _deep_seed_queue_payload(record) if record is not None else None

    def create_outbound_email_message(
        self,
        *,
        provider_message_id: str,
        provider_thread_id: str,
        email_thread_id: int,
        source_draft_id: int,
        from_address: str,
        to_addresses: tuple[str, ...],
        subject: str,
        body_text: str,
        received_at: datetime,
        normalized_at: datetime,
        source: str,
    ) -> MessageRecord:
        with self.session_factory() as session:
            record = SQLAlchemyEmailMessageRepository(session).create_outbound(
                NewOutboundEmailMessage(
                    provider_message_id=provider_message_id,
                    provider_thread_id=provider_thread_id,
                    email_thread_id=email_thread_id,
                    source_draft_id=source_draft_id,
                    from_address=from_address,
                    to_addresses=to_addresses,
                    subject=subject,
                    body_text=body_text,
                    received_at=received_at,
                    normalized_at=normalized_at,
                    source=source,
                )
            )
            return MessageRecord(id=record.id)

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
                    status=record.status,
                )
                for record in records
            ]

    def mark_task_completed(self, task_id: int) -> bool:
        with self.session_factory() as session:
            return SQLAlchemyScheduledThreadTaskRepository(session).mark_completed(task_id)

    def get_scheduled_task_by_id(self, task_id: int) -> ScheduledTaskRecord | None:
        with self.session_factory() as session:
            record = SQLAlchemyScheduledThreadTaskRepository(session).get_by_id(task_id)
            if record is None:
                return None
            return ScheduledTaskRecord(
                id=record.id,
                email_thread_id=record.email_thread_id,
                task_type=record.task_type,
                status=record.status,
            )

    def list_email_threads(
        self,
        *,
        business_state: str | None = None,
        label: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        with self.session_factory() as session:
            records = SQLAlchemyEmailThreadRepository(session).list_recent(
                business_state=business_state,
                label=label,
                limit=limit,
            )
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

    def list_email_proposals(
        self,
        *,
        status: str | None = None,
        proposal_type: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        with self.session_factory() as session:
            records = SQLAlchemyActionProposalRepository(session).list_recent(
                status=status,
                proposal_type=proposal_type,
                limit=limit,
            )
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

    def list_email_drafts(
        self,
        *,
        status: str | None = None,
        approval_status: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        with self.session_factory() as session:
            records = SQLAlchemyEmailDraftRepository(session).list_recent(
                status=status,
                approval_status=approval_status,
                limit=limit,
            )
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

    def list_classification_artifacts_for_thread(self, *, thread_id: int) -> list[dict]:
        with self.session_factory() as session:
            records = SQLAlchemyClassificationArtifactRepository(session).list_for_thread(
                email_thread_id=thread_id,
            )
            return [_classification_artifact_payload(record) for record in records]

    def list_classification_artifacts_for_message(self, *, message_id: int) -> list[dict]:
        with self.session_factory() as session:
            records = SQLAlchemyClassificationArtifactRepository(session).list_for_message(
                email_message_id=message_id,
            )
            return [_classification_artifact_payload(record) for record in records]

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

    def list_scheduled_tasks(
        self,
        *,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        with self.session_factory() as session:
            records = SQLAlchemyScheduledThreadTaskRepository(session).list_recent(
                status=status,
                limit=limit,
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


def build_email_agent_runtime(
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


def _classification_artifact_payload(record: object) -> dict:
    return {
        "id": record.id,
        "email_thread_id": record.email_thread_id,
        "email_message_id": record.email_message_id,
        "classification": record.classification,
        "priority_score": record.priority_score,
        "business_state": record.business_state,
        "visible_labels": record.visible_labels,
        "action_reason": record.action_reason,
        "resurfacing_source": record.resurfacing_source,
        "confidence_band": record.confidence_band,
        "decision_context": record.decision_context,
        "model_name": record.model_name,
        "prompt_version": record.prompt_version,
        "created_at": record.created_at,
    }


def _draft_reasoning_artifact_payload(record: object) -> dict:
    return {
        "id": record.id,
        "artifact_ref": record.internal_uuid,
        "email_draft_id": record.email_draft_id,
        "email_thread_id": record.email_thread_id,
        "action_proposal_id": record.action_proposal_id,
        "schema_version": record.schema_version,
        "prompt_context": record.prompt_context,
        "model_metadata": record.model_metadata,
        "reasoning_payload": record.reasoning_payload,
        "refinement_metadata": record.refinement_metadata,
        "created_at": record.created_at,
    }


def _deep_seed_queue_payload(record: object | None) -> dict | None:
    if record is None:
        return None
    return {
        "id": record.id,
        "source_type": record.source_type,
        "provider_thread_id": record.provider_thread_id,
        "status": record.status,
        "seed_reason": record.seed_reason,
        "message_count": record.message_count,
        "latest_received_at": record.latest_received_at,
        "sample_subject": record.sample_subject,
        "from_addresses": record.from_addresses,
        "thread_payload": record.thread_payload,
        "attempts": record.attempts,
        "last_error": record.last_error,
        "email_thread_id": record.email_thread_id,
        "completed_at": record.completed_at,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _create_draft_reasoning_artifact(
    *,
    session: Session,
    draft_id: int,
    email_thread_id: int,
    action_proposal_id: int | None,
    reasoning_artifact: dict[str, object],
):
    return SQLAlchemyDraftReasoningArtifactRepository(session).create(
        NewDraftReasoningArtifact(
            email_draft_id=draft_id,
            email_thread_id=email_thread_id,
            action_proposal_id=action_proposal_id,
            schema_version=str(reasoning_artifact["schema_version"]),
            prompt_context=_json_object(reasoning_artifact.get("prompt_context")),
            model_metadata=_json_object(reasoning_artifact.get("model_metadata")),
            reasoning_payload=_json_object(reasoning_artifact.get("reasoning_payload")),
            refinement_metadata=_json_object(reasoning_artifact.get("refinement_metadata")),
        )
    )


def _json_object(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    return {}
