from __future__ import annotations

from datetime import datetime

from app.engine.scheduler import next_review_date
from app.schemas.course import CourseState, TopicState
from app.schemas.session import ReviewResult, SessionRecord


def apply_review_to_topic(course: CourseState, topic_id: str, review: ReviewResult) -> TopicState:
    topic = next(topic for topic in course.topics if topic.id == topic_id)
    topic.mastery = max(0.0, min(1.0, topic.mastery + review.mastery_delta))
    topic.last_seen = datetime.now().date().isoformat()
    topic.next_review = next_review_date(topic, review.score)
    topic.confidence = review.confidence
    topic.weak_signals = _merge_signals(topic.weak_signals, review.weak_signals)
    topic.state = _derive_topic_state(topic.mastery, review.score)
    return topic


def finalize_session_record(record: SessionRecord, review: ReviewResult) -> SessionRecord:
    record.status = "completed"
    record.completed_at = datetime.now().isoformat(timespec="seconds")
    record.quiz_score = round(review.score, 2)
    record.review_summary = review.what_was_missing
    record.weak_signals = review.weak_signals
    record.next_step = review.next_step
    return record


def _merge_signals(existing: list[str], new_signals: list[str]) -> list[str]:
    merged = list(existing)
    for signal in new_signals:
        if signal not in merged:
            merged.append(signal)
    return merged[:8]


def _derive_topic_state(mastery: float, score: float) -> str:
    if mastery >= 0.8 and score >= 0.75:
        return "solid"
    if mastery < 0.4 or score < 0.45:
        return "shaky"
    return "learning"
