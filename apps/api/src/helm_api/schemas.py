from datetime import datetime

from pydantic import BaseModel


class StatusResponse(BaseModel):
    service: str
    state: str
    recent_failed_runs: int = 0


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


class AgentRunFailureResponse(BaseModel):
    id: int
    agent_name: str
    source_type: str
    source_id: str | None
    status: str
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None
