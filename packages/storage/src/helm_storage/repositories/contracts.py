from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from helm_storage.models import (
    ActionItemORM,
    ActionProposalORM,
    DigestItemORM,
    DraftReplyORM,
    EmailAgentConfigORM,
    EmailDraftORM,
    EmailThreadORM,
    ScheduledThreadTaskORM,
    WorkflowApprovalCheckpointORM,
    WorkflowArtifactORM,
    WorkflowEventORM,
    WorkflowRunORM,
    WorkflowSpecialistInvocationORM,
    WorkflowSyncRecordORM,
    WorkflowStepORM,
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
    last_history_cursor: str | None = None


class WorkflowRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    FAILED = "failed"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class WorkflowStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    VALIDATION_FAILED = "validation_failed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowArtifactType(StrEnum):
    RAW_REQUEST = "raw_request"
    NORMALIZED_TASK = "normalized_task"
    SCHEDULE_PROPOSAL = "schedule_proposal"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_DECISION = "approval_decision"
    REVISION_REQUEST = "revision_request"
    VALIDATION_RESULT = "validation_result"
    FINAL_SUMMARY = "final_summary"


class WorkflowSyncStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_TERMINAL = "failed_terminal"
    UNCERTAIN_NEEDS_RECONCILIATION = "uncertain_needs_reconciliation"
    CANCELLED = "cancelled"


class WorkflowTargetSystem(StrEnum):
    TASK_SYSTEM = "task_system"
    CALENDAR_SYSTEM = "calendar_system"


class WorkflowSyncKind(StrEnum):
    TASK_UPSERT = "task_upsert"
    CALENDAR_BLOCK_UPSERT = "calendar_block_upsert"


class WorkflowBlockedReason(StrEnum):
    VALIDATION_FAILED = "validation_failed"
    APPROVAL_REQUIRED = "approval_required"
    EXECUTION_FAILED = "execution_failed"


@dataclass(frozen=True, slots=True)
class RawRequestArtifactPayload:
    request_text: str
    submitted_by: str
    channel: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_text": self.request_text,
            "submitted_by": self.submitted_by,
            "channel": self.channel,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class NormalizedTaskArtifactPayload:
    title: str
    summary: str
    tasks: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "tasks": list(self.tasks),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class ValidationArtifactPayload:
    outcome: str
    summary: str
    validator_name: str
    schema_version: str
    issues: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "summary": self.summary,
            "validator_name": self.validator_name,
            "schema_version": self.schema_version,
            "issues": list(self.issues),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class ScheduleProposalArtifactPayload:
    proposal_summary: str
    calendar_id: str | None
    time_blocks: tuple[dict[str, Any], ...]
    proposed_changes: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_summary": self.proposal_summary,
            "calendar_id": self.calendar_id,
            "time_blocks": list(self.time_blocks),
            "proposed_changes": list(self.proposed_changes),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class WorkflowSyncPayload:
    proposal_artifact_id: int
    proposal_version_number: int
    target_system: str
    sync_kind: str
    planned_item_key: str
    payload: dict[str, Any]
    payload_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_artifact_id": self.proposal_artifact_id,
            "proposal_version_number": self.proposal_version_number,
            "target_system": self.target_system,
            "sync_kind": self.sync_kind,
            "planned_item_key": self.planned_item_key,
            "payload": self.payload,
            "payload_fingerprint": self.payload_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class WorkflowSummaryArtifactPayload:
    request_artifact_id: int
    intermediate_artifact_ids: tuple[int, ...]
    validation_artifact_ids: tuple[int, ...]
    final_summary_text: str
    approval_decision: str | None = None
    approval_decision_artifact_id: int | None = None
    downstream_sync_status: str | None = None
    downstream_sync_artifact_ids: tuple[int, ...] = ()
    downstream_sync_reference_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_artifact_id": self.request_artifact_id,
            "intermediate_artifact_ids": list(self.intermediate_artifact_ids),
            "validation_artifact_ids": list(self.validation_artifact_ids),
            "final_summary_text": self.final_summary_text,
            "approval_decision": self.approval_decision,
            "approval_decision_artifact_id": self.approval_decision_artifact_id,
            "downstream_sync_status": self.downstream_sync_status,
            "downstream_sync_artifact_ids": list(self.downstream_sync_artifact_ids),
            "downstream_sync_reference_ids": list(self.downstream_sync_reference_ids),
        }


@dataclass(frozen=True, slots=True)
class ApprovalRequestArtifactPayload:
    checkpoint_id: int
    target_artifact_id: int
    target_version_number: int
    allowed_actions: tuple[str, ...]
    pause_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "target_artifact_id": self.target_artifact_id,
            "target_version_number": self.target_version_number,
            "allowed_actions": list(self.allowed_actions),
            "pause_reason": self.pause_reason,
        }


@dataclass(frozen=True, slots=True)
class ApprovalDecisionArtifactPayload:
    checkpoint_id: int
    target_artifact_id: int
    target_version_number: int
    decision: str
    actor: str
    decision_at: datetime
    revision_feedback: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "target_artifact_id": self.target_artifact_id,
            "target_version_number": self.target_version_number,
            "decision": self.decision,
            "actor": self.actor,
            "decision_at": self.decision_at.isoformat(),
            "revision_feedback": self.revision_feedback,
        }


@dataclass(frozen=True, slots=True)
class RevisionRequestArtifactPayload:
    checkpoint_id: int
    target_artifact_id: int
    target_version_number: int
    feedback: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "target_artifact_id": self.target_artifact_id,
            "target_version_number": self.target_version_number,
            "feedback": self.feedback,
        }


@dataclass(frozen=True, slots=True)
class NewWorkflowRun:
    workflow_type: str
    status: str = WorkflowRunStatus.PENDING.value
    current_step_name: str | None = None
    needs_action: bool = False
    current_step_attempt: int = 0
    attempt_count: int = 0
    validation_outcome_summary: str | None = None
    execution_error_summary: str | None = None
    blocked_reason: str | None = None
    failure_class: str | None = None
    retry_state: str | None = None
    resume_step_name: str | None = None
    resume_step_attempt: int | None = None
    last_event_summary: str | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowRunPatch:
    status: str | None = None
    current_step_name: str | None = None
    needs_action: bool | None = None
    current_step_attempt: int | None = None
    attempt_count: int | None = None
    validation_outcome_summary: str | None = None
    execution_error_summary: str | None = None
    blocked_reason: str | None = None
    failure_class: str | None = None
    retry_state: str | None = None
    resume_step_name: str | None = None
    resume_step_attempt: int | None = None
    last_event_summary: str | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class NewWorkflowStep:
    run_id: int
    step_name: str
    status: str = WorkflowStepStatus.RUNNING.value
    attempt_number: int = 1
    validation_outcome_summary: str | None = None
    execution_error_summary: str | None = None
    failure_class: str | None = None
    retry_state: str | None = None
    retryable: bool = False
    completed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowStepPatch:
    status: str | None = None
    validation_outcome_summary: str | None = None
    execution_error_summary: str | None = None
    failure_class: str | None = None
    retry_state: str | None = None
    retryable: bool | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class NewWorkflowArtifact:
    run_id: int
    artifact_type: str
    schema_version: str
    payload: dict[str, Any]
    step_id: int | None = None
    version_number: int | None = None
    producer_step_name: str | None = None
    lineage_parent_id: int | None = None
    supersedes_artifact_id: int | None = None


@dataclass(frozen=True, slots=True)
class NewWorkflowEvent:
    run_id: int
    event_type: str
    summary: str
    step_id: int | None = None
    run_status: str | None = None
    step_status: str | None = None
    details: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class NewWorkflowSpecialistInvocation:
    run_id: int
    step_id: int
    specialist_name: str
    input_artifact_id: int
    output_artifact_id: int | None = None
    status: str = "running"
    completed_at: datetime | None = None
    error_summary: str | None = None


@dataclass(frozen=True, slots=True)
class WorkflowSpecialistInvocationPatch:
    output_artifact_id: int | None = None
    status: str | None = None
    completed_at: datetime | None = None
    error_summary: str | None = None


@dataclass(frozen=True, slots=True)
class NewWorkflowApprovalCheckpoint:
    run_id: int
    step_id: int
    target_artifact_id: int
    resume_step_name: str
    allowed_actions: tuple[str, ...]
    resume_step_attempt: int = 1
    status: str = "pending"
    decision: str | None = None
    decision_actor: str | None = None
    decision_at: datetime | None = None
    revision_feedback: str | None = None
    resolved_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowApprovalCheckpointPatch:
    status: str | None = None
    decision: str | None = None
    decision_actor: str | None = None
    decision_at: datetime | None = None
    revision_feedback: str | None = None
    resolved_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowRunState:
    run: WorkflowRunORM
    current_step: WorkflowStepORM | None
    latest_artifacts: dict[str, WorkflowArtifactORM]
    last_event: WorkflowEventORM | None
    approval_checkpoints: tuple[WorkflowApprovalCheckpointORM, ...]
    active_approval_checkpoint: WorkflowApprovalCheckpointORM | None
    sync_records: tuple[WorkflowSyncRecordORM, ...] = ()


@dataclass(frozen=True, slots=True)
class NewWorkflowSyncRecord:
    run_id: int
    step_id: int
    proposal_artifact_id: int
    proposal_version_number: int
    target_system: str
    sync_kind: str
    planned_item_key: str
    execution_order: int
    idempotency_key: str
    payload_fingerprint: str
    payload: dict[str, Any]
    status: str = WorkflowSyncStatus.PENDING.value
    external_object_id: str | None = None
    last_error_summary: str | None = None
    attempt_count: int = 0
    last_attempt_step_id: int | None = None
    last_attempted_at: datetime | None = None
    completed_at: datetime | None = None
    supersedes_sync_record_id: int | None = None
    replayed_from_sync_record_id: int | None = None


@dataclass(frozen=True, slots=True)
class WorkflowSyncRecordPatch:
    status: str | None = None
    external_object_id: str | None = None
    last_error_summary: str | None = None
    attempt_count: int | None = None
    last_attempt_step_id: int | None = None
    last_attempted_at: datetime | None = None
    completed_at: datetime | None = None
    supersedes_sync_record_id: int | None = None
    replayed_from_sync_record_id: int | None = None


@dataclass(frozen=True, slots=True)
class WorkflowSyncClaimPatch:
    status: str = WorkflowSyncStatus.IN_PROGRESS.value
    attempt_count: int | None = None
    last_attempt_step_id: int | None = None
    last_attempted_at: datetime | None = None
    last_error_summary: str | None = None


@dataclass(frozen=True, slots=True)
class WorkflowSyncRemainingQuery:
    run_id: int
    statuses: tuple[str, ...] = (
        WorkflowSyncStatus.PENDING.value,
        WorkflowSyncStatus.IN_PROGRESS.value,
        WorkflowSyncStatus.FAILED_RETRYABLE.value,
        WorkflowSyncStatus.UNCERTAIN_NEEDS_RECONCILIATION.value,
    )


@dataclass(frozen=True, slots=True)
class WorkflowSyncFailedQuery:
    run_id: int
    statuses: tuple[str, ...] = (
        WorkflowSyncStatus.FAILED_RETRYABLE.value,
        WorkflowSyncStatus.FAILED_TERMINAL.value,
        WorkflowSyncStatus.UNCERTAIN_NEEDS_RECONCILIATION.value,
    )


@dataclass(frozen=True, slots=True)
class WorkflowSyncStepQuery:
    run_id: int
    step_name: str
    max_attempt_number: int
    statuses: tuple[str, ...] = (
        WorkflowSyncStatus.PENDING.value,
        WorkflowSyncStatus.IN_PROGRESS.value,
        WorkflowSyncStatus.FAILED_RETRYABLE.value,
        WorkflowSyncStatus.UNCERTAIN_NEEDS_RECONCILIATION.value,
    )


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
    def list_recent(self, *, limit: int | None = None) -> list[EmailThreadORM]: ...

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
    def list_recent(self, *, limit: int | None = None) -> list[ActionProposalORM]: ...

    def create(self, item: NewActionProposal) -> ActionProposalORM: ...

    def get_latest_for_thread(self, *, email_thread_id: int) -> ActionProposalORM | None: ...


@runtime_checkable
class EmailDraftRepository(Protocol):
    def list_recent(self, *, limit: int | None = None) -> list[EmailDraftORM]: ...

    def create(self, item: NewEmailDraft) -> EmailDraftORM: ...

    def get_by_id(self, draft_id: int) -> EmailDraftORM | None: ...

    def get_latest_for_thread(self, *, email_thread_id: int) -> EmailDraftORM | None: ...

    def set_approval_status(self, draft_id: int, *, approval_status: str) -> bool: ...


@runtime_checkable
class ScheduledThreadTaskRepository(Protocol):
    def create(self, item: NewScheduledThreadTask) -> ScheduledThreadTaskORM: ...

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


@runtime_checkable
class WorkflowRunRepository(Protocol):
    def create(self, run: NewWorkflowRun) -> WorkflowRunORM: ...

    def get_by_id(self, run_id: int) -> WorkflowRunORM | None: ...

    def update(self, run_id: int, patch: WorkflowRunPatch) -> WorkflowRunORM | None: ...

    def get_with_current_state(self, run_id: int) -> WorkflowRunState | None: ...

    def list_needing_action(self, *, limit: int | None = None) -> list[WorkflowRunState]: ...

    def list_runnable(self, *, limit: int | None = None) -> list[WorkflowRunState]: ...


@runtime_checkable
class WorkflowStepRepository(Protocol):
    def create(self, step: NewWorkflowStep) -> WorkflowStepORM: ...

    def update(self, step_id: int, patch: WorkflowStepPatch) -> WorkflowStepORM | None: ...

    def list_for_run(self, run_id: int) -> list[WorkflowStepORM]: ...

    def get_last_for_run(self, run_id: int, *, step_name: str | None = None) -> WorkflowStepORM | None: ...

    def get_last_failed_for_run(self, run_id: int) -> WorkflowStepORM | None: ...


@runtime_checkable
class WorkflowArtifactRepository(Protocol):
    def create(self, artifact: NewWorkflowArtifact) -> WorkflowArtifactORM: ...

    def get_by_id(self, artifact_id: int) -> WorkflowArtifactORM | None: ...

    def list_for_run(self, run_id: int) -> list[WorkflowArtifactORM]: ...

    def list_for_run_by_type(self, run_id: int, *, artifact_type: str) -> list[WorkflowArtifactORM]: ...

    def get_latest_for_run(self, run_id: int, *, artifact_type: str | None = None) -> WorkflowArtifactORM | None: ...

    def get_latest_by_type(self, run_id: int) -> dict[str, WorkflowArtifactORM]: ...


@runtime_checkable
class WorkflowEventRepository(Protocol):
    def create(self, event: NewWorkflowEvent) -> WorkflowEventORM: ...

    def list_for_run(self, run_id: int) -> list[WorkflowEventORM]: ...

    def list_for_run_by_type(self, run_id: int, *, event_type: str) -> list[WorkflowEventORM]: ...


@runtime_checkable
class WorkflowSpecialistInvocationRepository(Protocol):
    def create(self, invocation: NewWorkflowSpecialistInvocation) -> WorkflowSpecialistInvocationORM: ...

    def update(
        self,
        invocation_id: int,
        patch: WorkflowSpecialistInvocationPatch,
    ) -> WorkflowSpecialistInvocationORM | None: ...


@runtime_checkable
class WorkflowApprovalCheckpointRepository(Protocol):
    def create(self, checkpoint: NewWorkflowApprovalCheckpoint) -> WorkflowApprovalCheckpointORM: ...

    def update(
        self,
        checkpoint_id: int,
        patch: WorkflowApprovalCheckpointPatch,
    ) -> WorkflowApprovalCheckpointORM | None: ...

    def get_by_id(self, checkpoint_id: int) -> WorkflowApprovalCheckpointORM | None: ...

    def get_active_for_run(self, run_id: int) -> WorkflowApprovalCheckpointORM | None: ...

    def list_for_run(self, run_id: int) -> list[WorkflowApprovalCheckpointORM]: ...


@runtime_checkable
class WorkflowSyncRecordRepository(Protocol):
    def create(self, sync_record: NewWorkflowSyncRecord) -> WorkflowSyncRecordORM: ...

    def get_by_id(self, sync_record_id: int) -> WorkflowSyncRecordORM | None: ...

    def get_by_identity(
        self,
        *,
        proposal_artifact_id: int,
        proposal_version_number: int,
        target_system: str,
        sync_kind: str,
        planned_item_key: str,
    ) -> WorkflowSyncRecordORM | None: ...

    def list_for_run(self, run_id: int) -> list[WorkflowSyncRecordORM]: ...

    def list_for_proposal(self, proposal_artifact_id: int) -> list[WorkflowSyncRecordORM]: ...

    def list_remaining(self, query: WorkflowSyncRemainingQuery) -> list[WorkflowSyncRecordORM]: ...

    def list_failed(self, query: WorkflowSyncFailedQuery) -> list[WorkflowSyncRecordORM]: ...

    def list_for_step_attempt(self, query: WorkflowSyncStepQuery) -> list[WorkflowSyncRecordORM]: ...

    def claim_next_pending(
        self,
        *,
        run_id: int,
        step_id: int,
        step_name: str,
        step_attempt_number: int,
    ) -> WorkflowSyncRecordORM | None: ...

    def mark_attempt_started(
        self,
        sync_record_id: int,
        *,
        step_id: int,
        attempted_at: datetime | None = None,
    ) -> WorkflowSyncRecordORM | None: ...

    def mark_succeeded(
        self,
        sync_record_id: int,
        *,
        external_object_id: str | None = None,
        completed_at: datetime | None = None,
    ) -> WorkflowSyncRecordORM | None: ...

    def mark_failed(
        self,
        sync_record_id: int,
        *,
        status: str,
        error_summary: str | None,
        completed_at: datetime | None = None,
        external_object_id: str | None = None,
    ) -> WorkflowSyncRecordORM | None: ...

    def update(
        self,
        sync_record_id: int,
        patch: WorkflowSyncRecordPatch,
    ) -> WorkflowSyncRecordORM | None: ...
