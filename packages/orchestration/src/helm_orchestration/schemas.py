from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


SCHEMA_VERSION = "2026-03-13"


class ValidationOutcome(StrEnum):
    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    FAILED = "failed"


class RetryState(StrEnum):
    RETRYABLE = "retryable"
    AWAITING_OPERATOR = "awaiting_operator"
    TERMINAL = "terminal"


class ApprovalAction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_REVISION = "request_revision"


class ApprovalCheckpointStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"


class SyncTargetSystem(StrEnum):
    TASK_SYSTEM = "task_system"
    CALENDAR_SYSTEM = "calendar_system"


class SyncOperation(StrEnum):
    TASK_UPSERT = "task_upsert"
    CALENDAR_BLOCK_UPSERT = "calendar_block_upsert"


class SyncOutcomeStatus(StrEnum):
    SUCCEEDED = "succeeded"
    RETRYABLE_FAILURE = "retryable_failure"
    TERMINAL_FAILURE = "terminal_failure"
    RECONCILIATION_REQUIRED = "reconciliation_required"


class SyncRetryDisposition(StrEnum):
    RETRYABLE = "retryable"
    TERMINAL = "terminal"
    RECONCILE = "reconcile"


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    path: tuple[str, ...] = ()
    blocking: bool = True
    context: dict[str, Any] = Field(default_factory=dict)


class TaskArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    summary: str
    priority: str | None = None
    estimated_minutes: int | None = None
    deadline: str | None = None
    dependencies: tuple[str, ...] = ()


class RawWorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_text: str
    submitted_by: str
    channel: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskAgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_type: str
    run_id: int
    step_name: str
    request_artifact_id: int
    request_text: str
    submitted_by: str
    channel: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    constraints: tuple[str, ...] = ()


class NormalizedTaskArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    summary: str
    tasks: tuple[TaskArtifact, ...]
    warnings: tuple[str, ...] = ()


class TaskAgentOutput(NormalizedTaskArtifact):
    model_config = ConfigDict(extra="forbid")


class ScheduleBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    start: str
    end: str
    task_title: str | None = None


class CalendarAgentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_type: str
    run_id: int
    step_name: str
    normalized_task_artifact_id: int
    tasks: tuple[TaskArtifact, ...]
    scheduling_constraints: tuple[str, ...] = ()
    source_context: dict[str, Any] = Field(default_factory=dict)
    request_text: str | None = None
    warnings: tuple[str, ...] = ()
    revision_request_artifact_id: int | None = None
    revision_feedback: str | None = None
    prior_proposal_artifact_id: int | None = None
    prior_proposal_version: int | None = None


class ScheduleProposalArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_summary: str
    calendar_id: str | None = None
    time_blocks: tuple[ScheduleBlock, ...]
    proposed_changes: tuple[str, ...]
    warnings: tuple[str, ...] = ()


class CalendarAgentOutput(ScheduleProposalArtifact):
    model_config = ConfigDict(extra="forbid")


class ApprovedSyncItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_artifact_id: int
    proposal_version_number: int
    target_system: SyncTargetSystem
    operation: SyncOperation
    planned_item_key: str
    execution_order: int
    payload_fingerprint: str
    payload: dict[str, Any] = Field(default_factory=dict)


class SyncLookupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_artifact_id: int
    proposal_version_number: int
    target_system: SyncTargetSystem
    operation: SyncOperation
    planned_item_key: str
    payload_fingerprint: str
    external_object_id: str | None = None


class SyncLookupResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool
    external_object_id: str | None = None
    provider_state: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class TaskSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: ApprovedSyncItem


class TaskSyncResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SyncOutcomeStatus
    retry_disposition: SyncRetryDisposition
    external_object_id: str | None = None
    error_summary: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class CalendarSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: ApprovedSyncItem


class CalendarSyncResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SyncOutcomeStatus
    retry_disposition: SyncRetryDisposition
    external_object_id: str | None = None
    error_summary: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checkpoint_id: int
    run_id: int
    target_artifact_id: int
    target_version_number: int
    proposal_summary: str
    allowed_actions: tuple[ApprovalAction, ...]
    pause_reason: str


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ApprovalAction
    actor: str
    target_artifact_id: int
    revision_feedback: str | None = None


class ApprovalDecisionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checkpoint_id: int
    action: ApprovalAction
    actor: str
    target_artifact_id: int
    decision_at: str
    resumed_step_name: str | None = None


class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: ValidationOutcome
    summary: str
    validator_name: str
    schema_version: str = SCHEMA_VERSION
    issues: tuple[ValidationIssue, ...] = ()
    warnings: tuple[str, ...] = ()


class ExecutionFailurePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_type: str
    message: str
    retry_state: RetryState
    retryable: bool
    details: dict[str, Any] = Field(default_factory=dict)


class WorkflowSummaryArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_artifact_id: int
    intermediate_artifact_ids: tuple[int, ...]
    validation_artifact_ids: tuple[int, ...]
    final_summary_text: str
    approval_decision: str | None = None
    approval_decision_artifact_id: int | None = None
    downstream_sync_status: str | None = None
    downstream_sync_artifact_ids: tuple[int, ...] = ()
    downstream_sync_reference_ids: tuple[str, ...] = ()
