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


class DraftTransitionAuditResponse(BaseModel):
    id: int
    draft_id: int
    action: str
    from_status: str | None
    to_status: str | None
    success: bool
    reason: str | None = None
    created_at: datetime


class DraftReasoningArtifactResponse(BaseModel):
    id: int
    artifact_ref: str
    email_draft_id: int
    email_thread_id: int
    action_proposal_id: int | None = None
    schema_version: str
    prompt_context: dict[str, object] = Field(default_factory=dict)
    model_metadata: dict[str, object] = Field(default_factory=dict)
    reasoning_payload: dict[str, object] = Field(default_factory=dict)
    refinement_metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class EmailSendAttemptResponse(BaseModel):
    id: int
    draft_id: int
    email_thread_id: int
    attempt_number: int
    status: str
    failure_class: str | None = None
    failure_message: str | None = None
    provider_error_code: str | None = None
    provider_message_id: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class EmailDraftDetailResponse(BaseModel):
    id: int
    email_thread_id: int
    action_proposal_id: int | None = None
    status: str
    approval_status: str
    draft_body: str
    draft_subject: str | None = None
    draft_reasoning_artifact_ref: str | None = None
    final_sent_message_id: int | None = None
    transition_audits: list[DraftTransitionAuditResponse] = Field(default_factory=list)
    reasoning_artifacts: list[DraftReasoningArtifactResponse] = Field(default_factory=list)
    send_attempts: list[EmailSendAttemptResponse] = Field(default_factory=list)


class EmailMessageResponse(BaseModel):
    id: int
    provider_message_id: str
    provider_thread_id: str
    direction: str
    from_address: str
    subject: str
    snippet: str | None = None
    received_at: datetime
    processed_at: datetime | None = None
    source: str


class EmailThreadDetailResponse(BaseModel):
    thread: EmailThreadResponse
    proposals: list[EmailProposalResponse] = Field(default_factory=list)
    drafts: list[EmailDraftResponse] = Field(default_factory=list)
    messages: list[EmailMessageResponse] = Field(default_factory=list)


class ClassificationArtifactResponse(BaseModel):
    id: int
    email_thread_id: int
    email_message_id: int
    classification: str
    priority_score: int
    business_state: str
    visible_labels: list[str] = Field(default_factory=list)
    action_reason: str | None = None
    resurfacing_source: str | None = None
    confidence_band: str | None = None
    decision_context: dict[str, object] = Field(default_factory=dict)
    model_name: str | None = None
    prompt_version: str | None = None
    created_at: datetime


class EmailThreadReprocessRequest(BaseModel):
    dry_run: bool = True


class EmailThreadReprocessResponse(BaseModel):
    status: str
    thread_id: int
    dry_run: bool
    found: bool
    reprocessed: bool
    reason: str | None = None
    workflow_status: str | None = None


class SendDraftResponse(BaseModel):
    status: str
    draft_id: int
    attempt_id: int | None
    sent: bool
    reason: str | None = None
    warning: str | None = None
    final_sent_message_id: int | None = None


class EmailConfigResponse(BaseModel):
    approval_required_before_send: bool
    default_follow_up_business_days: int
    timezone_name: str
    last_history_cursor: str | None = None


class UpdateEmailConfigRequest(BaseModel):
    approval_required_before_send: bool | None = None
    default_follow_up_business_days: int | None = Field(default=None, ge=0)
    timezone_name: str | None = None


class UpdateEmailConfigResponse(BaseModel):
    status: str
    reason: str | None = None
    config: EmailConfigResponse | None = None


class EmailThreadOverrideRequest(BaseModel):
    business_state: str = Field(
        pattern="^(uninitialized|waiting_on_user|waiting_on_other_party|needs_review|resolved)$"
    )
    visible_labels: list[str] = Field(default_factory=list)
    current_summary: str | None = None
    latest_confidence_band: str | None = None
    action_reason: str | None = None


class EmailThreadOverrideResponse(BaseModel):
    status: str
    thread_id: int
    found: bool
    reason: str | None = None
    thread: EmailThreadResponse | None = None


class EmailManualMessageRequest(BaseModel):
    id: str
    threadId: str | None = None
    from_address: str | None = Field(default=None, alias="from")
    subject: str = ""
    body_text: str = ""
    snippet: str | None = None
    received_at: datetime | None = None

    model_config = {"populate_by_name": True}


class EmailIngestRequest(BaseModel):
    source_type: str = "email_manual"
    messages: list[EmailManualMessageRequest]


class EmailIngestResponse(BaseModel):
    status: str
    source_type: str
    message_count: int
    persisted: bool
    thread_count: int
    processed_count: int
    failed_message_count: int = 0
    normalization_failures: dict[str, int] = Field(default_factory=dict)


class SeedThreadDecisionResponse(BaseModel):
    provider_thread_id: str
    bucket: str
    reason: str
    message_count: int
    latest_received_at: datetime
    sample_subject: str
    from_addresses: list[str] = Field(default_factory=list)


class EmailSeedPlanResponse(BaseModel):
    status: str
    source_type: str
    message_count: int
    thread_count: int
    failed_message_count: int = 0
    normalization_failures: dict[str, int] = Field(default_factory=dict)
    bucket_counts: dict[str, int] = Field(default_factory=dict)
    bucket_thread_ids: dict[str, list[str]] = Field(default_factory=dict)
    decisions: list[SeedThreadDecisionResponse] = Field(default_factory=list)


class EmailDeepSeedQueueResponse(BaseModel):
    id: int
    source_type: str
    provider_thread_id: str
    status: str
    seed_reason: str
    message_count: int
    latest_received_at: datetime
    sample_subject: str
    from_addresses: list[str] = Field(default_factory=list)
    attempts: int
    last_error: str | None = None
    email_thread_id: int | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class EmailSeedEnqueueResponse(EmailSeedPlanResponse):
    enqueued_count: int = 0
    skipped_count: int = 0
    queued_thread_ids: list[str] = Field(default_factory=list)


class ScheduledTaskResponse(BaseModel):
    id: int
    email_thread_id: int
    task_type: str
    created_by: str
    due_at: datetime
    status: str
    reason: str | None = None


class CreateScheduledTaskRequest(BaseModel):
    task_type: str = Field(pattern="^(reminder|followup)$")
    due_at: datetime
    created_by: str = "user"


class CreateScheduledTaskResponse(BaseModel):
    status: str
    thread_id: int
    task_id: int | None
    reason: str | None = None


class CompleteScheduledTaskResponse(BaseModel):
    status: str
    thread_id: int
    task_id: int
    completed: bool
    reason: str | None = None




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


class ReplayQueueItemResponse(BaseModel):
    id: int
    agent_run_id: int | None = None
    source_type: str
    source_id: str | None = None
    status: str
    attempts: int
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class ReplayRequeueResponse(BaseModel):
    status: str
    replay_id: int
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


class JobControlResponse(BaseModel):
    job_name: str
    paused: bool


class JobControlListResponse(BaseModel):
    items: list[JobControlResponse]


class ReplayJobRunRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=100)


class ReplayJobRunResponse(BaseModel):
    status: str
    job_name: str
    limit: int
    processed_count: int
    reason: str | None = None


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
