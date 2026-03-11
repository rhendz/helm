from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(slots=True, frozen=True)
class MessageRecord:
    id: int


@dataclass(slots=True, frozen=True)
class MessageProcessingRecord:
    id: int
    direction: str
    processed_at: datetime | None


@dataclass(slots=True, frozen=True)
class RunRecord:
    id: int


@dataclass(slots=True, frozen=True)
class ThreadRecord:
    id: int
    business_state: str
    visible_labels: str
    current_summary: str | None
    latest_confidence_band: str | None
    resurfacing_source: str | None
    action_reason: str | None
    last_message_id: int | None
    last_inbound_message_id: int | None
    last_outbound_message_id: int | None


@dataclass(slots=True, frozen=True)
class ProposalRecord:
    id: int


@dataclass(slots=True, frozen=True)
class DraftRecord:
    id: int


@dataclass(slots=True, frozen=True)
class DigestRecord:
    id: int


@dataclass(slots=True, frozen=True)
class ScheduledTaskRecord:
    id: int
    email_thread_id: int
    task_type: str
    status: str


@dataclass(slots=True, frozen=True)
class ClassificationArtifactRecord:
    id: int


@dataclass(slots=True, frozen=True)
class DraftReasoningArtifactRecord:
    id: int
    artifact_ref: str


@dataclass(slots=True, frozen=True)
class SendAttemptRecord:
    id: int


@dataclass(slots=True, frozen=True)
class DeepSeedQueueRecord:
    id: int


@dataclass(slots=True, frozen=True)
class EmailAgentConfigRecord:
    approval_required_before_send: bool
    default_follow_up_business_days: int
    timezone_name: str
    last_history_cursor: str | None


class EmailAgentRuntime(Protocol):
    def start_run(
        self,
        *,
        agent_name: str,
        source_type: str,
        source_id: str | None,
    ) -> RunRecord: ...

    def mark_run_succeeded(self, run_id: int) -> None: ...

    def mark_run_failed(self, run_id: int, error_message: str) -> None: ...

    def get_or_create_thread(self, *, provider_thread_id: str) -> ThreadRecord: ...

    def get_thread_by_id(self, thread_id: int) -> ThreadRecord | None: ...

    def get_thread_by_provider_thread_id(self, provider_thread_id: str) -> ThreadRecord | None: ...

    def get_message_by_provider_message_id(
        self,
        provider_message_id: str,
    ) -> MessageProcessingRecord | None: ...

    def upsert_inbound_message(
        self,
        *,
        message: object,
        email_thread_id: int,
    ) -> MessageRecord: ...

    def mark_message_processed(
        self,
        provider_message_id: str,
        *,
        processed_at: datetime,
    ) -> None: ...

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
    ) -> ThreadRecord | None: ...

    def get_latest_proposal_for_thread(
        self,
        *,
        email_thread_id: int,
    ) -> ProposalRecord | None: ...

    def create_proposal(
        self,
        *,
        email_thread_id: int,
        proposal_type: str,
        rationale: str | None,
        confidence_band: str | None,
    ) -> ProposalRecord: ...

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
    ) -> ClassificationArtifactRecord: ...

    def get_latest_email_draft_for_thread(
        self,
        *,
        email_thread_id: int,
    ) -> DraftRecord | None: ...

    def create_email_draft(
        self,
        *,
        email_thread_id: int,
        action_proposal_id: int | None,
        draft_body: str,
        draft_subject: str | None,
        reasoning_artifact: dict[str, object] | None = None,
    ) -> DraftRecord: ...

    def update_email_draft(
        self,
        *,
        draft_id: int,
        email_thread_id: int,
        action_proposal_id: int | None,
        draft_body: str,
        draft_subject: str | None,
        reasoning_artifact: dict[str, object] | None = None,
    ) -> DraftRecord | None: ...

    def get_email_draft_by_id(self, draft_id: int) -> dict | None: ...

    def list_draft_reasoning_artifacts_for_draft(self, *, draft_id: int) -> list[dict]: ...

    def list_draft_transition_audits_for_draft(self, *, draft_id: int) -> list[dict]: ...

    def list_send_attempts_for_draft(self, *, draft_id: int) -> list[dict]: ...

    def set_email_draft_approval_status(
        self,
        draft_id: int,
        *,
        approval_status: str,
    ) -> bool: ...

    def set_email_draft_status(self, draft_id: int, *, status: str) -> bool: ...

    def set_email_draft_final_sent_message(self, draft_id: int, *, message_id: int) -> bool: ...

    def create_draft_transition_audit(
        self,
        *,
        draft_id: int,
        action: str,
        from_status: str | None,
        to_status: str | None,
        success: bool,
        reason: str | None,
    ) -> None: ...

    def find_matching_digest(
        self,
        *,
        domain: str,
        title: str,
        summary: str,
    ) -> DigestRecord | None: ...

    def create_digest(
        self,
        *,
        domain: str,
        title: str,
        summary: str,
        priority: int,
    ) -> DigestRecord: ...

    def get_send_attempt_count_for_draft(self, *, draft_id: int) -> int: ...

    def has_successful_send_for_draft(self, *, draft_id: int) -> bool: ...

    def create_send_attempt(
        self,
        *,
        draft_id: int,
        email_thread_id: int,
        attempt_number: int,
        started_at: datetime,
    ) -> SendAttemptRecord: ...

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
    ) -> SendAttemptRecord | None: ...

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
    ) -> tuple[DeepSeedQueueRecord, bool]: ...

    def list_deep_seed_queue(
        self,
        *,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict]: ...

    def mark_deep_seed_item_processing(self, item_id: int) -> dict | None: ...

    def mark_deep_seed_item_completed(
        self,
        item_id: int,
        *,
        email_thread_id: int | None,
        completed_at: datetime,
    ) -> dict | None: ...

    def mark_deep_seed_item_failed(self, item_id: int, *, error_message: str) -> dict | None: ...

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
    ) -> MessageRecord: ...

    def get_email_agent_config(self) -> EmailAgentConfigRecord: ...

    def update_email_agent_config(
        self,
        *,
        approval_required_before_send: bool | None = None,
        default_follow_up_business_days: int | None = None,
        timezone_name: str | None = None,
        last_history_cursor: str | None = None,
    ) -> EmailAgentConfigRecord: ...

    def list_due_tasks(
        self,
        *,
        due_before: datetime,
        limit: int = 100,
    ) -> list[ScheduledTaskRecord]: ...

    def mark_task_completed(self, task_id: int) -> bool: ...

    def get_scheduled_task_by_id(self, task_id: int) -> ScheduledTaskRecord | None: ...

    def list_email_threads(
        self,
        *,
        business_state: str | None = None,
        label: str | None = None,
        limit: int = 20,
    ) -> list[dict]: ...

    def list_email_proposals(
        self,
        *,
        status: str | None = None,
        proposal_type: str | None = None,
        limit: int = 20,
    ) -> list[dict]: ...

    def list_email_drafts(
        self,
        *,
        status: str | None = None,
        approval_status: str | None = None,
        limit: int = 20,
    ) -> list[dict]: ...

    def list_classification_artifacts_for_thread(self, *, thread_id: int) -> list[dict]: ...

    def list_classification_artifacts_for_message(self, *, message_id: int) -> list[dict]: ...

    def get_email_thread_detail(self, *, thread_id: int) -> dict | None: ...

    def get_latest_inbound_email_message(self, *, thread_id: int) -> dict | None: ...

    def get_latest_outbound_email_message(self, *, thread_id: int) -> dict | None: ...

    def list_scheduled_tasks_for_thread(self, *, thread_id: int) -> list[dict]: ...

    def list_scheduled_tasks(
        self,
        *,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict]: ...

    def create_scheduled_task(
        self,
        *,
        thread_id: int,
        task_type: str,
        created_by: str,
        due_at: datetime,
        reason: str | None,
    ) -> dict: ...
