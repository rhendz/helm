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


class ScheduleProposalArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_summary: str
    calendar_id: str | None = None
    time_blocks: tuple[ScheduleBlock, ...]
    proposed_changes: tuple[str, ...]
    warnings: tuple[str, ...] = ()


class CalendarAgentOutput(ScheduleProposalArtifact):
    model_config = ConfigDict(extra="forbid")


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
