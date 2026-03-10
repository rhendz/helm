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
    previous_topic: TopicState | None = None,
) -> str:
    filename = f"{date.today().isoformat()}-{course.course_id}-{topic.id}.md"
    path = user_dir(user_id) / "sessions" / filename
    old_mastery = previous_topic.mastery if previous_topic else topic.mastery
    old_state = previous_topic.state if previous_topic else topic.state
    breakdown = session.recommendation_breakdown
    course_priority = breakdown.course_priority if breakdown else 0.0
    due_review = breakdown.due_review if breakdown else 0.0
    recovery_pressure = breakdown.recovery_pressure if breakdown else 0.0
    consolidation_pressure = breakdown.consolidation_pressure if breakdown else 0.0
    advancement_pressure = breakdown.advancement_pressure if breakdown else 0.0
    progression_bonus = breakdown.progression_bonus if breakdown else 0.0
    cooldown_penalty = breakdown.cooldown_penalty if breakdown else 0.0
    content = f"""
# Session: {course.title} - {topic.name}

- Course: {course.title}
- Topic: {topic.name}
- Mode: {session.mode}
- Policy stage: {session.policy_stage or "unknown"}
- Score: {review.score:.2f}
- Recommendation reason: {session.recommendation_reason or "No recommendation reason stored."}

## Corrected Mini Notes

{review.corrected_notes}

## What You Got Right

{review.what_was_right}

## What Was Missing

{review.what_was_missing}

## Weak Areas

{_render_list(review.weak_signals)}

## Structured Residue

- State change: {old_state} -> {topic.state}
- Mastery change: {old_mastery:.2f} -> {topic.mastery:.2f}
- Next review: {topic.next_review or "not scheduled"}
- Cooldown until: {topic.cooldown_until or "none"}
- Breakdown:
  - course_priority: {course_priority:.2f}
  - due_review: {due_review:.2f}
  - recovery_pressure: {recovery_pressure:.2f}
  - consolidation_pressure: {consolidation_pressure:.2f}
  - advancement_pressure: {advancement_pressure:.2f}
  - progression_bonus: {progression_bonus:.2f}
  - cooldown_penalty: {cooldown_penalty:.2f}

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
