from pydantic import BaseModel


class StatusResponse(BaseModel):
    service: str
    state: str


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
    study_session_id: int
    summary: str
    learning_task_ids: list[int]
    knowledge_gap_ids: list[int]
    digest_item_id: int | None
    agent_run_id: int
