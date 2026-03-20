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


class RecoveryClassification(StrEnum):
    RECOVERABLE_FAILURE = "recoverable_failure"
    TERMINAL_FAILURE = "terminal_failure"
    RETRY_REQUESTED = "retry_requested"
    REPLAY_REQUESTED = "replay_requested"
    TERMINATED_AFTER_PARTIAL_SUCCESS = "terminated_after_partial_success"


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    path: tuple[str, ...] = ()
    blocking: bool = True
    context: dict[str, Any] = Field(default_factory=dict)


class TaskSemantics(BaseModel):
    model_config = ConfigDict(extra="ignore")  # NOT "forbid" — LLM may add fields

    urgency: str  # low / medium / high
    priority: str  # low / medium / high
    sizing_minutes: int
    confidence: float  # 0.0–1.0
    suggested_date: str | None = None  # ISO date string e.g. "2026-03-21", None if not inferable


class TaskArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    summary: str
    priority: str | None = None
    estimated_minutes: int | None = None
    deadline: str | None = None
    dependencies: tuple[str, ...] = ()
    source_line: str | None = None
    warnings: tuple[str, ...] = ()


class WeeklyTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    details: str | None = None
    priority: str | None = None
    deadline: str | None = None
    estimated_minutes: int | None = None
    source_line: str | None = None
    warnings: tuple[str, ...] = ()
    urgency: str | None = None
    confidence: float | None = None


class WeeklySchedulingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_request_text: str
    planning_goal: str | None = None
    tasks: tuple[WeeklyTaskRequest, ...] = ()
    protected_time: tuple[str, ...] = ()
    no_meeting_windows: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class RawWorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_text: str
    submitted_by: str
    channel: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    weekly_request: WeeklySchedulingRequest | None = None


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
    weekly_request: WeeklySchedulingRequest | None = None


class NormalizedTaskArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    summary: str
    tasks: tuple[TaskArtifact, ...]
    request_summary: str | None = None
    protected_time: tuple[str, ...] = ()
    no_meeting_windows: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
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
    weekly_request: WeeklySchedulingRequest | None = None
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
    honored_constraints: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    carry_forward_tasks: tuple[str, ...] = ()
    rationale: tuple[str, ...] = ()
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
    calendar_id: str = "primary"  # staging calendar override for E2E


class SyncLookupResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool
    external_object_id: str | None = None
    payload_fingerprint_matches: bool | None = None
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


class RecoveryTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sync_record_id: int
    planned_item_key: str
    classification: RecoveryClassification
    prior_status: str | None = None
    next_status: str
    details: dict[str, Any] = Field(default_factory=dict)


class ReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: int
    actor: str
    requested_at: str
    reason: str
    source_sync_record_ids: tuple[int, ...]
    replay_sync_record_ids: tuple[int, ...]


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
