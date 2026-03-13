from datetime import datetime

from pydantic import BaseModel, Field


class StatusResponse(BaseModel):
    service: str
    state: str
    recent_failed_runs: int = 0
    paused_jobs: list[str] = Field(default_factory=list)


class ActionItemResponse(BaseModel):
    id: int
    title: str
    priority: int
    status: str


class DraftResponse(BaseModel):
    id: int
    channel_type: str
    status: str
    preview: str
    is_stale: bool = False


class EmailThreadResponse(BaseModel):
    id: int
    provider_thread_id: str
    business_state: str
    visible_labels: list[str] = Field(default_factory=list)
    current_summary: str | None = None
    latest_confidence_band: str | None = None
    resurfacing_source: str | None = None
    action_reason: str | None = None


class EmailProposalResponse(BaseModel):
    id: int
    email_thread_id: int
    proposal_type: str
    status: str
    confidence_band: str | None = None
    rationale: str | None = None


class EmailDraftResponse(BaseModel):
    id: int
    email_thread_id: int
    action_proposal_id: int | None = None
    status: str
    approval_status: str
    preview: str
    draft_subject: str | None = None


class StudyIngestRequest(BaseModel):
    source_type: str = "manual"
    raw_text: str


class StudyIngestResponse(BaseModel):
    status: str
    source_type: str
    chars: int
    summary: str
    task_count: int
    gap_count: int
    session_id: int | None
    persisted: bool


class AgentRunFailureResponse(BaseModel):
    id: int
    agent_name: str
    source_type: str
    source_id: str | None
    status: str
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None


class DraftTransitionFailureResponse(BaseModel):
    id: int
    draft_id: int
    action: str
    from_status: str | None
    to_status: str | None
    success: bool
    reason: str | None
    created_at: datetime


class ReplayEnqueueRequest(BaseModel):
    agent_run_id: int


class ReplayEnqueueResponse(BaseModel):
    status: str
    replay_id: int | None
    created: bool
    reason: str | None = None


class ReplayReprocessRequest(BaseModel):
    source_type: str | None = None
    source_id: str | None = None
    since_hours: int | None = Field(default=None, ge=1, le=168)
    limit: int = Field(default=20, ge=1, le=100)
    dry_run: bool = True


class ReplayReprocessResponse(BaseModel):
    status: str
    dry_run: bool
    matched_count: int
    enqueued_count: int
    skipped_count: int
    reason: str | None = None


class WorkflowReplayRequest(BaseModel):
    actor: str
    reason: str = Field(min_length=1)


class WorkflowReplayResponse(BaseModel):
    status: str
    run_id: int
    source_sync_record_ids: list[int] = Field(default_factory=list)
    replay_sync_record_ids: list[int] = Field(default_factory=list)
    replay_queue_source_ids: list[str] = Field(default_factory=list)
    run: dict[str, object] = Field(default_factory=dict)
    reason: str | None = None


class JobControlResponse(BaseModel):
    job_name: str
    paused: bool


class JobControlListResponse(BaseModel):
    items: list[JobControlResponse]


class DraftRequeueRequest(BaseModel):
    stale_after_hours: int = Field(default=72, ge=1, le=720)
    limit: int = Field(default=20, ge=1, le=100)
    dry_run: bool = True


class DraftRequeueResponse(BaseModel):
    status: str
    stale_after_hours: int
    dry_run: bool
    matched_count: int
    requeued_count: int
    draft_ids: list[int] = Field(default_factory=list)


class ArtifactTracePointerResponse(BaseModel):
    key: str
    value: str


class ArtifactTraceRunResponse(BaseModel):
    id: int
    agent_name: str
    status: str
    source_type: str
    source_id: str | None
    started_at: datetime
    completed_at: datetime | None
    error_present: bool


class ArtifactTraceResponse(BaseModel):
    status: str
    artifact_type: str
    artifact_id: int
    source_pointers: list[ArtifactTracePointerResponse] = Field(default_factory=list)
    run_context: list[ArtifactTraceRunResponse] = Field(default_factory=list)
    reason: str | None = None


class WeeklyTaskRequestResponse(BaseModel):
    title: str
    details: str | None = None
    priority: str | None = None
    deadline: str | None = None
    estimated_minutes: int | None = None
    source_line: str | None = None
    warnings: list[str] = Field(default_factory=list)


class WeeklySchedulingRequestResponse(BaseModel):
    raw_request_text: str
    planning_goal: str | None = None
    tasks: list[WeeklyTaskRequestResponse] = Field(default_factory=list)
    protected_time: list[str] = Field(default_factory=list)
    no_meeting_windows: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WorkflowRunCreateRequest(BaseModel):
    workflow_type: str = "weekly_scheduling"
    first_step_name: str = "dispatch_task_agent"
    request_text: str
    submitted_by: str
    channel: str
    metadata: dict[str, object] = Field(default_factory=dict)


class WorkflowRunActionRequest(BaseModel):
    reason: str


class WorkflowApprovalDecisionRequest(BaseModel):
    actor: str
    target_artifact_id: int = Field(gt=0)
    feedback: str | None = None


class WorkflowAvailableActionResponse(BaseModel):
    action: str
    label: str


class WorkflowApprovalCheckpointResponse(BaseModel):
    checkpoint_id: int
    target_artifact_id: int
    target_version_number: int
    proposal_summary: str | None = None
    time_blocks: list[dict[str, object]] = Field(default_factory=list)
    proposed_changes: list[str] = Field(default_factory=list)
    honored_constraints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    carry_forward_tasks: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)
    pause_reason: str
    allowed_actions: list[str] = Field(default_factory=list)


class WorkflowApprovalDecisionResponse(BaseModel):
    decision: str
    actor: str
    target_artifact_id: int
    target_version_number: int | None = None
    decision_at: str
    revision_feedback: str | None = None


class WorkflowProposalVersionResponse(BaseModel):
    artifact_id: int
    version_number: int
    proposal_summary: str | None = None
    time_blocks: list[dict[str, object]] = Field(default_factory=list)
    proposed_changes: list[str] = Field(default_factory=list)
    honored_constraints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    carry_forward_tasks: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)
    created_at: datetime
    producer_step_name: str | None = None
    is_latest: bool = False
    is_actionable: bool = False
    superseded: bool = False
    approved: bool = False
    rejected: bool = False
    latest_decision: WorkflowApprovalDecisionResponse | None = None
    revision_feedback_summary: str | None = None
    supersedes_artifact_id: int | None = None


class WorkflowCompletionSummaryResponse(BaseModel):
    headline: str
    approval_decision: str | None = None
    downstream_sync_status: str | None = None
    scheduled_block_count: int = 0
    scheduled_highlights: list[str] = Field(default_factory=list)
    total_sync_writes: int = 0
    task_sync_writes: int = 0
    calendar_sync_writes: int = 0
    carry_forward_tasks: list[str] = Field(default_factory=list)
    attention_items: list[str] = Field(default_factory=list)


class WorkflowRunSummaryResponse(BaseModel):
    id: int
    workflow_type: str
    status: str
    current_step: str | None = None
    current_step_attempt: int
    attempt_count: int
    needs_action: bool
    paused_state: str | None = None
    pause_reason: str | None = None
    last_event_summary: str | None = None
    failure_summary: str | None = None
    failure_kind: str | None = None
    latest_validation_outcome: str | None = None
    retry_state: str | None = None
    retryable: bool
    available_actions: list[WorkflowAvailableActionResponse] = Field(default_factory=list)
    approval_checkpoint: WorkflowApprovalCheckpointResponse | None = None
    latest_decision: WorkflowApprovalDecisionResponse | None = None
    latest_proposal_version: WorkflowProposalVersionResponse | None = None
    proposal_versions: list[WorkflowProposalVersionResponse] = Field(default_factory=list)
    weekly_request: WeeklySchedulingRequestResponse | None = None
    completion_summary: WorkflowCompletionSummaryResponse | None = None
    effect_summary: dict[str, object] | None = None
    sync: dict[str, object] = Field(default_factory=dict)
    safe_next_actions: list[WorkflowAvailableActionResponse] = Field(default_factory=list)
    recovery_class: str | None = None
    started_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class WorkflowArtifactLinkResponse(BaseModel):
    artifact_id: int
    artifact_type: str
    schema_version: str
    version_number: int
    step_id: int | None = None
    producer_step_name: str | None = None
    lineage_parent_id: int | None = None
    supersedes_artifact_id: int | None = None
    payload: dict[str, object]
    created_at: datetime


class WorkflowStepTransitionResponse(BaseModel):
    id: int
    step_name: str
    attempt_number: int
    status: str
    retry_state: str | None = None
    retryable: bool
    validation_outcome_summary: str | None = None
    execution_error_summary: str | None = None
    failure_class: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class WorkflowEventResponse(BaseModel):
    id: int
    event_type: str
    run_status: str | None = None
    step_status: str | None = None
    step_id: int | None = None
    summary: str
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class WorkflowFinalSummaryResponse(BaseModel):
    artifact_id: int | None = None
    request_artifact_id: int | None = None
    intermediate_artifact_ids: list[int] = Field(default_factory=list)
    validation_artifact_ids: list[int] = Field(default_factory=list)
    final_summary_text: str | None = None
    approval_decision: str | None = None
    approval_decision_artifact_id: int | None = None
    downstream_sync_status: str | None = None
    downstream_sync_artifact_ids: list[int] = Field(default_factory=list)
    downstream_sync_reference_ids: list[str] = Field(default_factory=list)


class WorkflowLineageResponse(BaseModel):
    raw_request: WorkflowArtifactLinkResponse | None = None
    intermediate_artifacts: list[WorkflowArtifactLinkResponse] = Field(default_factory=list)
    validation_artifacts: list[WorkflowArtifactLinkResponse] = Field(default_factory=list)
    final_summary: WorkflowFinalSummaryResponse = Field(default_factory=WorkflowFinalSummaryResponse)
    step_transitions: list[WorkflowStepTransitionResponse] = Field(default_factory=list)
    events: list[WorkflowEventResponse] = Field(default_factory=list)


class WorkflowRunDetailResponse(WorkflowRunSummaryResponse):
    lineage: WorkflowLineageResponse
