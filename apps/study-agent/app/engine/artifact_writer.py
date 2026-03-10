from __future__ import annotations

from datetime import date

from app.schemas.course import CourseState, TopicState
from app.schemas.session import ReviewResult, SessionRecord
from app.storage.files import user_dir, write_markdown


def write_session_artifact(
    user_id: str,
    course: CourseState,
    topic: TopicState,
    session: SessionRecord,
    review: ReviewResult,
) -> str:
    filename = f"{date.today().isoformat()}-{course.course_id}-{topic.id}.md"
    path = user_dir(user_id) / "sessions" / filename
    content = f"""
# Session: {course.title} - {topic.name}

- Course: {course.title}
- Topic: {topic.name}
- Mode: {session.mode}
- Score: {review.score:.2f}

## Corrected Mini Notes

{review.corrected_notes}

## What You Got Right

{review.what_was_right}

## What Was Missing

{review.what_was_missing}

## Weak Areas

{_render_list(review.weak_signals)}

## Next Step

{review.next_step}
"""
    write_markdown(path, content)
    return str(path)


def write_weekly_checkin_artifact(
    user_id: str,
    iso_week: str,
    adherence_summary: str,
    complaints: str,
    reprioritization: str,
    mastery_corrections: str,
    cadence_notes: str,
    next_week_focus: str,
) -> str:
    path = user_dir(user_id) / "weekly_reviews" / f"{iso_week}.md"
    content = f"""
# Weekly Check-In {iso_week}

## Adherence Summary

{adherence_summary}

## Complaints

{complaints}

## Reprioritization Decisions

{reprioritization}

## Mastery Corrections

{mastery_corrections}

## Cadence Notes

{cadence_notes}

## Next-Week Focus

{next_week_focus}
"""
    write_markdown(path, content)
    return str(path)


def _render_list(items: list[str]) -> str:
    if not items:
        return "- None surfaced."
    return "\n".join(f"- {item}" for item in items)
