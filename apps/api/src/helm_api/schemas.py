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


class LinkedInManualEventRequest(BaseModel):
    id: str
    thread_id: str | None = None
    sender_name: str = ""
    body_text: str = ""
    received_at: datetime | None = None


class LinkedInIngestRequest(BaseModel):
    source_type: str = "linkedin_manual"
    events: list[LinkedInManualEventRequest]


class LinkedInIngestResponse(BaseModel):
    status: str
    source_type: str
    event_count: int
    persisted: bool
    message_count: int
    thread_count: int
    failed_event_count: int = 0
    normalization_failures: dict[str, int] = Field(default_factory=dict)


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
