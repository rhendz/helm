from __future__ import annotations

from datetime import date

from app.schemas.course import CourseState, TopicState
from app.schemas.session import Recommendation


def choose_recommendation(courses: list[CourseState]) -> Recommendation:
    today = date.today()
    best_course: CourseState | None = None
    best_topic: TopicState | None = None
    best_score = float("-inf")
    best_reason = ""

    for course in courses:
        topic, due_for_review = _pick_topic(course, today)
        score = _score_course(course, topic, due_for_review, today)
        if score > best_score:
            best_score = score
            best_course = course
            best_topic = topic
            best_reason = _build_reason(course, topic, due_for_review)

    if best_course is None or best_topic is None:
        raise ValueError("No active course recommendation could be created")

    mode = "lite" if _should_use_lite(best_course) else "full"
    return Recommendation(
        course_id=best_course.course_id,
        course_title=best_course.title,
        topic_id=best_topic.id,
        topic_name=best_topic.name,
        mode=mode,
        reason=best_reason,
        score=best_score,
    )


def _pick_topic(course: CourseState, today: date) -> tuple[TopicState, bool]:
    due_topics = [topic for topic in course.topics if _is_due(topic, today)]
    if due_topics:
        chosen = sorted(
            due_topics,
            key=lambda topic: (topic.mastery, len(topic.weak_signals), topic.name),
        )[0]
        return chosen, True

    chosen = sorted(
        course.topics,
        key=lambda topic: (
            topic.state != "unseen",
            topic.mastery,
            -len(topic.weak_signals),
            topic.name,
        ),
    )[0]
    return chosen, False


def _score_course(
    course: CourseState,
    topic: TopicState,
    due_for_review: bool,
    today: date,
) -> float:
    score = float(course.priority * 10)
    score += max(0.0, (1.0 - topic.mastery) * 8)
    score += len(topic.weak_signals) * 1.5
    if due_for_review:
        score += 20
    score += course.adherence.miss_streak * 2
    if course.adherence.missed > course.adherence.completed:
        score += 3
    deadline = course.cadence.get("deadline")
    if deadline:
        days_left = (date.fromisoformat(deadline) - today).days
        if days_left <= 14:
            score += 8
        elif days_left <= 30:
            score += 4
    if topic.state == "unseen":
        score += 2
    return score


def _build_reason(course: CourseState, topic: TopicState, due_for_review: bool) -> str:
    reasons = [f"{course.title} has the highest priority"]
    if due_for_review:
        reasons.append(f"{topic.name} is due for review")
    if topic.weak_signals:
        reasons.append(f"{topic.name} still has weak spots")
    if course.adherence.miss_streak:
        reasons.append("recent misses mean momentum matters more than intensity")
    return ", ".join(reasons) + "."


def _should_use_lite(course: CourseState) -> bool:
    return course.adherence.miss_streak >= 1 or course.adherence.missed > course.adherence.completed


def _is_due(topic: TopicState, today: date) -> bool:
    if not topic.next_review:
        return False
    return date.fromisoformat(topic.next_review) <= today
