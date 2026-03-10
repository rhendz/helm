from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class SessionRecord(BaseModel):
    session_id: str
    course_id: str
    topic_id: str
    mode: str
    status: str
    started_at: str
    completed_at: str | None = None
    quiz_score: float | None = None
    review_summary: str | None = None
    weak_signals: list[str] = Field(default_factory=list)
    next_step: str | None = None

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        if value not in {"full", "lite"}:
            raise ValueError(f"Invalid mode: {value}")
        return value


class ReviewResult(BaseModel):
    score: float
    what_was_right: str
    what_was_missing: str
    stronger_answer_guidance: str
    weak_signals: list[str] = Field(default_factory=list)
    next_step: str
    mastery_delta: float = 0.0
    confidence: str = "medium"
    corrected_notes: str


class Recommendation(BaseModel):
    course_id: str
    course_title: str
    topic_id: str
    topic_name: str
    mode: str
    reason: str
    score: float


class ActiveSessionContext(BaseModel):
    session_id: str
    user_id: str
    course_id: str
    topic_id: str
    topic_name: str
    course_title: str
    mode: str
    teaching_text: str
    quiz_text: str
    started_at: str


class CheckinState(BaseModel):
    user_id: str
    started_at: str
    current_index: int
    questions: list[str]
    answers: list[str] = Field(default_factory=list)
