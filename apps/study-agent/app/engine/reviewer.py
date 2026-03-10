from __future__ import annotations

from app.engine.rules import apply_session_completion
from app.schemas.course import CourseState
from app.schemas.session import ReviewResult, SessionRecord


def apply_review_outcome(
    course: CourseState,
    topic_id: str,
    session: SessionRecord,
    review: ReviewResult,
    *,
    now,
) -> tuple[CourseState, SessionRecord]:
    return apply_session_completion(course, topic_id, session, review, now=now)
