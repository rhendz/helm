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
