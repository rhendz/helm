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
