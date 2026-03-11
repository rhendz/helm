from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from helm_storage.models import (
    ActionItemORM,
    ActionProposalORM,
    ClassificationArtifactORM,
    DigestItemORM,
    DraftReasoningArtifactORM,
    DraftReplyORM,
    EmailAgentConfigORM,
    EmailDeepSeedQueueORM,
    EmailDraftORM,
    EmailSendAttemptORM,
    EmailThreadORM,
    ScheduledThreadTaskORM,
)


@dataclass(frozen=True, slots=True)
class NewActionItem:
    source_type: str
    source_id: str | None
    title: str
    description: str | None = None
    priority: int = 3
    status: str = "open"
    due_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class NewDraftReply:
    channel_type: str = "email"
    thread_id: str | None = None
    contact_id: int | None = None
    draft_text: str = ""
    tone: str | None = None
    status: str = "pending"


@dataclass(frozen=True, slots=True)
class NewDigestItem:
    domain: str
    title: str
    summary: str
    priority: int = 3
    related_contact_id: int | None = None
    related_action_id: int | None = None


@dataclass(frozen=True, slots=True)
class NewEmailThread:
    provider_thread_id: str
    business_state: str = "uninitialized"
    visible_labels: tuple[str, ...] = ()
    current_summary: str | None = None
    latest_confidence_band: str | None = None
    resurfacing_source: str | None = None
    action_reason: str | None = None


@dataclass(frozen=True, slots=True)
class NewActionProposal:
    email_thread_id: int
    proposal_type: str
    rationale: str | None = None
    confidence_band: str | None = None
    status: str = "proposed"
    model_name: str | None = None
    prompt_version: str | None = None


@dataclass(frozen=True, slots=True)
class NewClassificationArtifact:
    email_thread_id: int
    email_message_id: int
    classification: str
    priority_score: int
    business_state: str
    visible_labels: tuple[str, ...]
    action_reason: str | None = None
    resurfacing_source: str | None = None
    confidence_band: str | None = None
    decision_context: dict[str, object] | None = None
    model_name: str | None = None
    prompt_version: str | None = None


@dataclass(frozen=True, slots=True)
class NewEmailDraft:
    email_thread_id: int
    draft_body: str
    action_proposal_id: int | None = None
    draft_subject: str | None = None
    status: str = "generated"
    approval_status: str = "pending_user"
    model_name: str | None = None
    prompt_version: str | None = None
    draft_reasoning_artifact_ref: str | None = None


@dataclass(frozen=True, slots=True)
class EmailDraftContentPatch:
    draft_body: str
    draft_subject: str | None
    action_proposal_id: int | None = None
    status: str | None = None
    approval_status: str | None = None
    model_name: str | None = None
    prompt_version: str | None = None
    draft_reasoning_artifact_ref: str | None = None


@dataclass(frozen=True, slots=True)
class NewDraftReasoningArtifact:
    email_draft_id: int
    email_thread_id: int
    schema_version: str
    prompt_context: dict[str, object]
    model_metadata: dict[str, object]
    reasoning_payload: dict[str, object]
    action_proposal_id: int | None = None
    refinement_metadata: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class NewEmailSendAttempt:
    draft_id: int
    email_thread_id: int
    attempt_number: int
    started_at: datetime
    status: str = "pending"
    failure_class: str | None = None
    failure_message: str | None = None
    provider_error_code: str | None = None
    provider_message_id: str | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class EmailSendAttemptPatch:
    status: str
    completed_at: datetime
    failure_class: str | None = None
    failure_message: str | None = None
    provider_error_code: str | None = None
    provider_message_id: str | None = None


@dataclass(frozen=True, slots=True)
class NewOutboundEmailMessage:
    provider_message_id: str
    provider_thread_id: str
    email_thread_id: int
    source_draft_id: int
    from_address: str
    to_addresses: tuple[str, ...]
    subject: str
    body_text: str
    received_at: datetime
    normalized_at: datetime
    source: str = "gmail"


@dataclass(frozen=True, slots=True)
class NewEmailDeepSeedQueueItem:
    source_type: str
    provider_thread_id: str
    seed_reason: str
    message_count: int
    latest_received_at: datetime
    sample_subject: str
    from_addresses: tuple[str, ...]
    thread_payload: list[dict[str, object]]
    status: str = "pending"
    attempts: int = 0


@dataclass(frozen=True, slots=True)
class EmailDeepSeedQueuePatch:
    status: str
    attempts: int | None = None
    last_error: str | None = None
    email_thread_id: int | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class NewScheduledThreadTask:
    email_thread_id: int
    task_type: str
    created_by: str
    due_at: datetime
    status: str = "pending"
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class EmailAgentConfigPatch:
    approval_required_before_send: bool | None = None
    default_follow_up_business_days: int | None = None
    timezone_name: str | None = None
    last_history_cursor: str | None = None


@runtime_checkable
class ActionItemRepository(Protocol):
    def list_open(self, *, limit: int | None = None) -> list[ActionItemORM]: ...

    def get_by_id(self, action_id: int) -> ActionItemORM | None: ...

    def get_open_by_source(self, *, source_type: str, source_id: str) -> ActionItemORM | None: ...

    def create(self, item: NewActionItem) -> ActionItemORM: ...


@runtime_checkable
class DraftReplyRepository(Protocol):
    def list_pending(self, *, limit: int | None = None) -> list[DraftReplyORM]: ...

    def list_stale(
        self,
        *,
        stale_after_hours: int = 72,
        include_snoozed: bool = True,
        limit: int | None = None,
        now: datetime | None = None,
    ) -> list[DraftReplyORM]: ...

    def get_by_id(self, draft_id: int) -> DraftReplyORM | None: ...

    def get_latest_for_thread(self, *, thread_id: str) -> DraftReplyORM | None: ...

    def create(self, item: NewDraftReply) -> DraftReplyORM: ...

    def approve(self, draft_id: int) -> bool: ...

    def snooze(self, draft_id: int) -> bool: ...

    def requeue(self, draft_id: int) -> bool: ...


@runtime_checkable
class DigestItemRepository(Protocol):
    def list_top(self, *, limit: int = 10, domain: str | None = None) -> list[DigestItemORM]: ...

    def find_matching(
        self,
        *,
        domain: str,
        title: str,
        summary: str,
        related_action_id: int | None,
    ) -> DigestItemORM | None: ...

    def create(self, item: NewDigestItem) -> DigestItemORM: ...


@runtime_checkable
class EmailThreadRepository(Protocol):
    def list_recent(
        self,
        *,
        business_state: str | None = None,
        label: str | None = None,
        limit: int | None = None,
    ) -> list[EmailThreadORM]: ...

    def get_by_id(self, thread_id: int) -> EmailThreadORM | None: ...

    def get_by_provider_thread_id(self, provider_thread_id: str) -> EmailThreadORM | None: ...

    def create(self, item: NewEmailThread) -> EmailThreadORM: ...

    def get_or_create(self, item: NewEmailThread) -> EmailThreadORM: ...

    def update_state(
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
    ) -> EmailThreadORM | None: ...


@runtime_checkable
class ActionProposalRepository(Protocol):
    def list_recent(
        self,
        *,
        status: str | None = None,
        proposal_type: str | None = None,
        limit: int | None = None,
    ) -> list[ActionProposalORM]: ...

    def create(self, item: NewActionProposal) -> ActionProposalORM: ...

    def get_latest_for_thread(self, *, email_thread_id: int) -> ActionProposalORM | None: ...


@runtime_checkable
class EmailDraftRepository(Protocol):
    def list_recent(
        self,
        *,
        status: str | None = None,
        approval_status: str | None = None,
        limit: int | None = None,
    ) -> list[EmailDraftORM]: ...

    def create(self, item: NewEmailDraft) -> EmailDraftORM: ...

    def get_by_id(self, draft_id: int) -> EmailDraftORM | None: ...

    def get_latest_for_thread(self, *, email_thread_id: int) -> EmailDraftORM | None: ...

    def set_approval_status(self, draft_id: int, *, approval_status: str) -> bool: ...

    def update_content(
        self,
        draft_id: int,
        patch: EmailDraftContentPatch,
    ) -> EmailDraftORM | None: ...

    def set_reasoning_artifact_ref(self, draft_id: int, *, artifact_ref: str) -> bool: ...

    def set_status(self, draft_id: int, *, status: str) -> bool: ...

    def set_final_sent_message(self, draft_id: int, *, message_id: int) -> bool: ...


@runtime_checkable
class ClassificationArtifactRepository(Protocol):
    def create(self, item: NewClassificationArtifact) -> ClassificationArtifactORM: ...

    def list_for_thread(self, *, email_thread_id: int) -> list[ClassificationArtifactORM]: ...

    def list_for_message(self, *, email_message_id: int) -> list[ClassificationArtifactORM]: ...


@runtime_checkable
class DraftReasoningArtifactRepository(Protocol):
    def create(self, item: NewDraftReasoningArtifact) -> DraftReasoningArtifactORM: ...

    def list_for_draft(self, *, email_draft_id: int) -> list[DraftReasoningArtifactORM]: ...


@runtime_checkable
class EmailSendAttemptRepository(Protocol):
    def create(self, item: NewEmailSendAttempt) -> EmailSendAttemptORM: ...

    def get_by_id(self, attempt_id: int) -> EmailSendAttemptORM | None: ...

    def list_for_draft(self, *, draft_id: int) -> list[EmailSendAttemptORM]: ...

    def count_for_draft(self, *, draft_id: int) -> int: ...

    def get_success_for_draft(self, *, draft_id: int) -> EmailSendAttemptORM | None: ...

    def update(
        self,
        attempt_id: int,
        patch: EmailSendAttemptPatch,
    ) -> EmailSendAttemptORM | None: ...


@runtime_checkable
class EmailDeepSeedQueueRepository(Protocol):
    def enqueue(self, item: NewEmailDeepSeedQueueItem) -> tuple[EmailDeepSeedQueueORM, bool]: ...

    def get_by_id(self, item_id: int) -> EmailDeepSeedQueueORM | None: ...

    def get_active_for_provider_thread(
        self,
        *,
        source_type: str,
        provider_thread_id: str,
    ) -> EmailDeepSeedQueueORM | None: ...

    def list_recent(
        self,
        *,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[EmailDeepSeedQueueORM]: ...

    def mark_processing(self, item_id: int) -> EmailDeepSeedQueueORM | None: ...

    def mark_completed(
        self,
        item_id: int,
        *,
        email_thread_id: int | None,
        completed_at: datetime,
    ) -> EmailDeepSeedQueueORM | None: ...

    def mark_failed(self, item_id: int, *, error_message: str) -> EmailDeepSeedQueueORM | None: ...


@runtime_checkable
class ScheduledThreadTaskRepository(Protocol):
    def create(self, item: NewScheduledThreadTask) -> ScheduledThreadTaskORM: ...

    def get_by_id(self, task_id: int) -> ScheduledThreadTaskORM | None: ...

    def list_for_thread(self, *, email_thread_id: int) -> list[ScheduledThreadTaskORM]: ...

    def list_recent(
        self,
        *,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[ScheduledThreadTaskORM]: ...

    def list_due(
        self,
        *,
        due_before: datetime,
        status: str = "pending",
        limit: int | None = None,
    ) -> list[ScheduledThreadTaskORM]: ...

    def mark_completed(self, task_id: int) -> bool: ...


@runtime_checkable
class EmailAgentConfigRepository(Protocol):
    def get(self) -> EmailAgentConfigORM | None: ...

    def get_or_create(self) -> EmailAgentConfigORM: ...

    def update(self, patch: EmailAgentConfigPatch) -> EmailAgentConfigORM: ...
