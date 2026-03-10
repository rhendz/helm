from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

SCHEMA_VERSION = 3


class UserProfile(BaseModel):
    schema_version: int = SCHEMA_VERSION
    user_id: str
    name: str
    preferences: dict = Field(default_factory=dict)
    telegram_user_id: int | None = None


class ActiveCourses(BaseModel):
    schema_version: int = SCHEMA_VERSION
    active_courses: list[str]


class TopicPerformance(BaseModel):
    date: str
    mode: str
    score: float | None = None
    weak_signals: list[str] = Field(default_factory=list)
    outcome: str

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        if value not in {"full", "lite"}:
            raise ValueError(f"Invalid topic performance mode: {value}")
        return value

    @field_validator("outcome")
    @classmethod
    def validate_outcome(cls, value: str) -> str:
        allowed = {"completed_full", "completed_lite", "missed", "abandoned", "expired"}
        if value not in allowed:
            raise ValueError(f"Invalid topic performance outcome: {value}")
        return value


class CourseTopicDefinition(BaseModel):
    id: str
    name: str
    summary: str
    priority_within_course: int = 3
    prerequisites: list[str] = Field(default_factory=list)
    next_topics: list[str] = Field(default_factory=list)
    starter: bool = False
    review_weight: float = 1.0
    mode_preference: str = "either"
    group: str | None = None

    @field_validator("priority_within_course")
    @classmethod
    def validate_priority(cls, value: int) -> int:
        return max(1, min(5, int(value)))

    @field_validator("review_weight")
    @classmethod
    def validate_review_weight(cls, value: float) -> float:
        return max(0.5, min(2.0, float(value)))

    @field_validator("mode_preference")
    @classmethod
    def validate_mode_preference(cls, value: str) -> str:
        allowed = {"either", "full", "lite"}
        if value not in allowed:
            raise ValueError(f"Invalid topic mode preference: {value}")
        return value


class TopicState(BaseModel):
    id: str
    name: str
    state: str
    mastery: float
    confidence: str
    priority_within_course: int = 3
    prerequisites: list[str] = Field(default_factory=list)
    next_topics: list[str] = Field(default_factory=list)
    starter: bool = False
    review_weight: float = 1.0
    mode_preference: str = "either"
    group: str | None = None
    last_seen: str | None = None
    next_review: str | None = None
    cooldown_until: str | None = None
    weak_signals: list[str] = Field(default_factory=list)
    recent_history: list[TopicPerformance] = Field(default_factory=list)

    @field_validator("state")
    @classmethod
    def validate_state(cls, value: str) -> str:
        allowed = {"unseen", "learning", "shaky", "solid"}
        if value not in allowed:
            raise ValueError(f"Invalid topic state: {value}")
        return value

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: str) -> str:
        allowed = {"low", "medium", "high"}
        if value not in allowed:
            raise ValueError(f"Invalid topic confidence: {value}")
        return value

    @field_validator("priority_within_course")
    @classmethod
    def validate_priority(cls, value: int) -> int:
        return max(1, min(5, int(value)))

    @field_validator("review_weight")
    @classmethod
    def validate_review_weight(cls, value: float) -> float:
        return max(0.5, min(2.0, float(value)))

    @field_validator("mode_preference")
    @classmethod
    def validate_mode_preference(cls, value: str) -> str:
        allowed = {"either", "full", "lite"}
        if value not in allowed:
            raise ValueError(f"Invalid topic mode preference: {value}")
        return value


class AdherenceState(BaseModel):
    scheduled: int = 0
    completed_full: int = 0
    completed_lite: int = 0
    missed: int = 0
    abandoned: int = 0
    miss_streak: int = 0
    recent_miss_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def migrate_v1_completed(cls, data):
        if isinstance(data, dict) and "completed" in data:
            completed = int(data.pop("completed"))
            data.setdefault("completed_full", completed)
            data.setdefault("completed_lite", 0)
            data.setdefault("abandoned", 0)
        return data

    @property
    def completed_total(self) -> int:
        return self.completed_full + self.completed_lite


class CourseState(BaseModel):
    schema_version: int = SCHEMA_VERSION
    course_id: str
    title: str
    goal: str
    status: str
    priority: int
    cadence: dict = Field(default_factory=dict)
    adherence: AdherenceState
    topics: list[TopicState]
    last_session_date: str | None = None
    weekly_checkin_needed: bool
