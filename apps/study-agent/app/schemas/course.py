from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class UserProfile(BaseModel):
    user_id: str
    name: str
    preferences: dict = Field(default_factory=dict)


class ActiveCourses(BaseModel):
    active_courses: list[str]


class TopicState(BaseModel):
    id: str
    name: str
    state: str
    mastery: float
    confidence: str
    last_seen: str | None = None
    next_review: str | None = None
    weak_signals: list[str] = Field(default_factory=list)

    @field_validator("state")
    @classmethod
    def validate_state(cls, value: str) -> str:
        allowed = {"unseen", "learning", "shaky", "solid"}
        if value not in allowed:
            raise ValueError(f"Invalid topic state: {value}")
        return value


class AdherenceState(BaseModel):
    scheduled: int
    completed: int
    missed: int
    miss_streak: int
    recent_miss_reasons: list[str] = Field(default_factory=list)


class CourseState(BaseModel):
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
