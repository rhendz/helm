from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import COURSES_DIR
from app.schemas.course import (
    ActiveCourses,
    CourseState,
    CourseTopicDefinition,
    TopicState,
    UserProfile,
)
from app.storage.files import (
    ensure_directory,
    load_active_courses,
    load_user_profile,
    save_active_courses,
    save_course_state,
    save_user_profile,
    user_dir,
    write_json,
    write_markdown,
)


def create_local_course(
    *,
    user_id: str,
    course_id: str,
    title: str,
    goal: str,
    topics_file: Path,
    priority: int = 3,
    sessions_per_week: int = 3,
    target_minutes: int = 25,
    course_summary: str | None = None,
    rubric_text: str | None = None,
    sources_text: str | None = None,
) -> CourseState:
    topics = _load_topics(topics_file)
    _ensure_user_shell(user_id)
    _write_course_pack(
        course_id=course_id,
        title=title,
        goal=goal,
        topics=topics,
        course_summary=course_summary,
        rubric_text=rubric_text,
        sources_text=sources_text,
    )
    state = CourseState(
        course_id=course_id,
        title=title,
        goal=goal,
        status="active",
        priority=max(1, min(5, priority)),
        cadence={
            "sessions_per_week": max(1, sessions_per_week),
            "target_minutes": max(10, target_minutes),
            "deadline": None,
        },
        adherence={
            "scheduled": 0,
            "completed_full": 0,
            "completed_lite": 0,
            "missed": 0,
            "abandoned": 0,
            "miss_streak": 0,
            "recent_miss_reasons": [],
        },
        topics=[
            TopicState(
                id=topic.id,
                name=topic.name,
                state="unseen",
                mastery=0.05,
                confidence="low",
                priority_within_course=topic.priority_within_course,
                prerequisites=list(topic.prerequisites),
                next_topics=list(topic.next_topics),
                starter=topic.starter,
                review_weight=topic.review_weight,
                mode_preference=topic.mode_preference,
                group=topic.group,
                last_seen=None,
                next_review=None,
                cooldown_until=None,
                weak_signals=[],
                recent_history=[],
            )
            for topic in topics
        ],
        last_session_date=None,
        weekly_checkin_needed=True,
    )
    save_course_state(user_id, state)
    active = _load_or_initialize_active_courses(user_id)
    if course_id not in active.active_courses:
        active.active_courses.append(course_id)
        save_active_courses(user_id, active)
    return state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a local study-agent course and initial state."
    )
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--course-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--topics-file", required=True)
    parser.add_argument("--priority", type=int, default=3)
    parser.add_argument("--sessions-per-week", type=int, default=3)
    parser.add_argument("--target-minutes", type=int, default=25)
    parser.add_argument("--course-summary")
    parser.add_argument("--rubric")
    parser.add_argument("--sources")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    state = create_local_course(
        user_id=args.user_id,
        course_id=args.course_id,
        title=args.title,
        goal=args.goal,
        topics_file=Path(args.topics_file),
        priority=args.priority,
        sessions_per_week=args.sessions_per_week,
        target_minutes=args.target_minutes,
        course_summary=args.course_summary,
        rubric_text=args.rubric,
        sources_text=args.sources,
    )
    print(
        json.dumps(
            {
                "course_id": state.course_id,
                "title": state.title,
                "topics": [topic.id for topic in state.topics],
                "user_id": args.user_id,
            },
            indent=2,
        )
    )


def _load_topics(path: Path) -> list[CourseTopicDefinition]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [CourseTopicDefinition.model_validate(item) for item in payload]


def _write_course_pack(
    *,
    course_id: str,
    title: str,
    goal: str,
    topics: list[CourseTopicDefinition],
    course_summary: str | None,
    rubric_text: str | None,
    sources_text: str | None,
) -> None:
    course_dir = COURSES_DIR / course_id
    ensure_directory(course_dir)
    write_markdown(
        course_dir / "course.md",
        course_summary
        or (
            f"# {title}\n\nGoal: {goal}\n\n"
            "Use this course for steady, consistency-first study."
        ),
    )
    write_json(
        course_dir / "topics.json",
        [topic.model_dump() for topic in topics],
        backup=False,
    )
    write_markdown(
        course_dir / "rubric.md",
        rubric_text or "Explain the concept clearly, give one example, and name one tradeoff.",
        backup=False,
    )
    write_markdown(
        course_dir / "sources.md",
        sources_text or "Local course pack created through study-agent onboarding.",
        backup=False,
    )


def _ensure_user_shell(user_id: str) -> None:
    base = user_dir(user_id)
    ensure_directory(base / "course_state")
    ensure_directory(base / "sessions")
    ensure_directory(base / "weekly_reviews")
    ensure_directory(base / "recommendations")
    try:
        load_user_profile(user_id)
    except Exception:
        save_user_profile(
            UserProfile(
                user_id=user_id,
                name=user_id,
                preferences={"default_session_minutes": 25, "tone": "direct"},
                telegram_user_id=None,
            )
        )


def _load_or_initialize_active_courses(user_id: str) -> ActiveCourses:
    try:
        return load_active_courses(user_id)
    except Exception:
        active = ActiveCourses(active_courses=[])
        save_active_courses(user_id, active)
        return active


if __name__ == "__main__":
    main()
