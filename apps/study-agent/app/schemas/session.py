from __future__ import annotations

from app.schemas.course import SCHEMA_VERSION
from pydantic import BaseModel, Field, field_validator


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


class RecommendationBreakdown(BaseModel):
    course_priority: float = 0.0
    due_review: float = 0.0
    recovery_pressure: float = 0.0
    consolidation_pressure: float = 0.0
    advancement_pressure: float = 0.0
    weak_signal_pressure: float = 0.0
    recent_performance_pressure: float = 0.0
    miss_pressure: float = 0.0
    pace_pressure: float = 0.0
    deadline_pressure: float = 0.0
    starter_bonus: float = 0.0
    progression_bonus: float = 0.0
    review_weight_bonus: float = 0.0
    prerequisite_penalty: float = 0.0
    cooldown_penalty: float = 0.0
    stage_bias: float = 0.0
    total: float = 0.0


class RecommendationAlternative(BaseModel):
    course_id: str
    topic_id: str
    policy_stage: str
    score: float
    why_not: str


class RecommendationAudit(BaseModel):
    schema_version: int = SCHEMA_VERSION
    created_at: str
    course_id: str
    course_title: str
    topic_id: str
    topic_name: str
    mode: str
    policy_stage: str
    reason: str
    winning_factors: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    breakdown: RecommendationBreakdown
    alternatives: list[RecommendationAlternative] = Field(default_factory=list)

    @field_validator("policy_stage")
    @classmethod
    def validate_policy_stage(cls, value: str) -> str:
        if value not in {"recovery", "consolidation", "advancement"}:
            raise ValueError(f"Invalid recommendation policy stage: {value}")
        return value


class Recommendation(BaseModel):
    course_id: str
    course_title: str
    topic_id: str
    topic_name: str
    mode: str
    policy_stage: str
    reason: str
    score: float
    breakdown: RecommendationBreakdown
    audit: RecommendationAudit | None = None


class SessionRecord(BaseModel):
    schema_version: int = SCHEMA_VERSION
    session_id: str
    user_id: str
    course_id: str
    topic_id: str
    mode: str
    status: str
    started_at: str
    expires_at: str | None = None
    completed_at: str | None = None
    last_event_at: str | None = None
    quiz_score: float | None = None
    review_summary: str | None = None
    weak_signals: list[str] = Field(default_factory=list)
    next_step: str | None = None
    policy_stage: str | None = None
    recommendation_reason: str | None = None
    recommendation_breakdown: RecommendationBreakdown | None = None
    counts_toward_schedule: bool = True
    recovery_action: str | None = None
    resume_count: int = 0

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        if value not in {"full", "lite"}:
            raise ValueError(f"Invalid mode: {value}")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        allowed = {
            "recommended",
            "in_progress",
            "awaiting_answer",
            "completed",
            "abandoned",
            "expired",
        }
        if value not in allowed:
            raise ValueError(f"Invalid session status: {value}")
        return value

    @field_validator("policy_stage")
    @classmethod
    def validate_policy_stage(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in {"recovery", "consolidation", "advancement"}:
            raise ValueError(f"Invalid session policy stage: {value}")
        return value


class ActiveSessionContext(BaseModel):
    schema_version: int = SCHEMA_VERSION
    session_id: str
    user_id: str
    course_id: str
    topic_id: str
    topic_name: str
    course_title: str
    mode: str
    status: str
    started_at: str
    expires_at: str
    policy_stage: str
    teaching_text: str
    quiz_text: str
    reason: str
    breakdown: RecommendationBreakdown
    counts_toward_schedule: bool = True
    recovery_action: str | None = None
    resume_count: int = 0


class CheckinProposedChange(BaseModel):
    course_id: str
    field_path: str
    old_value: str
    new_value: str
    reason: str


class CheckinState(BaseModel):
    schema_version: int = SCHEMA_VERSION
    user_id: str
    started_at: str
    status: str
    current_index: int
    questions: list[str]
    answers: list[str] = Field(default_factory=list)
    proposed_changes: list[CheckinProposedChange] = Field(default_factory=list)
    summary: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in {"collecting", "awaiting_approval"}:
            raise ValueError(f"Invalid checkin status: {value}")
        return value
