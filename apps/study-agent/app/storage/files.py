from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.config import COURSES_DIR, DEMO_TEMPLATE_USER_ID, PROMPTS_DIR, USERS_DIR
from app.schemas.course import ActiveCourses, CourseState, CourseTopicDefinition, UserProfile
from app.schemas.session import (
    ActiveSessionContext,
    CheckinState,
    RecommendationAudit,
    SessionRecord,
)


class StateFileError(RuntimeError):
    pass


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict | list:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StateFileError(f"Missing state file: {path}") from exc
    except json.JSONDecodeError as exc:
        backup = backup_path(path)
        if backup.exists():
            try:
                return json.loads(backup.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        raise StateFileError(f"Corrupted state file: {path}") from exc


def backup_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".bak")


def write_json(path: Path, payload: dict | list, backup: bool = True) -> None:
    ensure_directory(path.parent)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    serialized = json.dumps(payload, indent=2)
    temp_path.write_text(serialized, encoding="utf-8")
    if backup and path.exists():
        shutil.copy2(path, backup_path(path))
    temp_path.replace(path)


def write_markdown(path: Path, content: str, backup: bool = False) -> None:
    ensure_directory(path.parent)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(content.strip() + "\n", encoding="utf-8")
    if backup and path.exists():
        shutil.copy2(path, backup_path(path))
    temp_path.replace(path)


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def load_course_pack(course_id: str) -> dict:
    course_dir = COURSES_DIR / course_id
    return {
        "course": (course_dir / "course.md").read_text(encoding="utf-8"),
        "topics": [
            CourseTopicDefinition.model_validate(item)
            for item in read_json(course_dir / "topics.json")
        ],
        "rubric": (course_dir / "rubric.md").read_text(encoding="utf-8"),
        "sources": (course_dir / "sources.md").read_text(encoding="utf-8"),
    }


def user_dir(user_id: str) -> Path:
    return USERS_DIR / user_id


def list_user_dirs() -> list[Path]:
    if not USERS_DIR.exists():
        return []
    return [path for path in USERS_DIR.iterdir() if path.is_dir()]


def load_user_profile(user_id: str) -> UserProfile:
    return UserProfile.model_validate(read_json(user_dir(user_id) / "profile.json"))


def save_user_profile(profile: UserProfile) -> None:
    write_json(user_dir(profile.user_id) / "profile.json", profile.model_dump())


def load_active_courses(user_id: str) -> ActiveCourses:
    return ActiveCourses.model_validate(read_json(user_dir(user_id) / "active_courses.json"))


def save_active_courses(user_id: str, active_courses: ActiveCourses) -> None:
    write_json(user_dir(user_id) / "active_courses.json", active_courses.model_dump())


def load_course_state(user_id: str, course_id: str) -> CourseState:
    path = user_dir(user_id) / "course_state" / f"{course_id}.json"
    state = CourseState.model_validate(read_json(path))
    return hydrate_course_state_metadata(state)


def save_course_state(user_id: str, state: CourseState) -> None:
    path = user_dir(user_id) / "course_state" / f"{state.course_id}.json"
    write_json(path, state.model_dump())


def list_course_states(user_id: str) -> list[CourseState]:
    active = load_active_courses(user_id)
    return [load_course_state(user_id, course_id) for course_id in active.active_courses]


def session_json_path(user_id: str, session_id: str) -> Path:
    return user_dir(user_id) / "sessions" / f"{session_id}.json"


def save_session_record(user_id: str, record: SessionRecord) -> None:
    write_json(session_json_path(user_id, record.session_id), record.model_dump())


def load_session_record(user_id: str, session_id: str) -> SessionRecord:
    return SessionRecord.model_validate(read_json(session_json_path(user_id, session_id)))


def active_session_path(user_id: str) -> Path:
    return user_dir(user_id) / "active_session.json"


def save_active_session(user_id: str, session: ActiveSessionContext) -> None:
    write_json(active_session_path(user_id), session.model_dump())


def load_active_session(user_id: str) -> ActiveSessionContext | None:
    path = active_session_path(user_id)
    if not path.exists():
        return None
    return ActiveSessionContext.model_validate(read_json(path))


def clear_active_session(user_id: str) -> None:
    path = active_session_path(user_id)
    if path.exists():
        path.unlink()


def active_checkin_path(user_id: str) -> Path:
    return user_dir(user_id) / "active_checkin.json"


def save_active_checkin(user_id: str, checkin: CheckinState) -> None:
    write_json(active_checkin_path(user_id), checkin.model_dump())


def load_active_checkin(user_id: str) -> CheckinState | None:
    path = active_checkin_path(user_id)
    if not path.exists():
        return None
    return CheckinState.model_validate(read_json(path))


def clear_active_checkin(user_id: str) -> None:
    path = active_checkin_path(user_id)
    if path.exists():
        path.unlink()


def recommendation_audit_dir(user_id: str) -> Path:
    return user_dir(user_id) / "recommendations"


def recommendation_audit_path(user_id: str, created_at: str, course_id: str, topic_id: str) -> Path:
    safe_timestamp = created_at.replace(":", "").replace("+", "_")
    return recommendation_audit_dir(user_id) / f"{safe_timestamp}-{course_id}-{topic_id}.json"


def save_recommendation_audit(user_id: str, audit: RecommendationAudit) -> str:
    path = recommendation_audit_path(user_id, audit.created_at, audit.course_id, audit.topic_id)
    write_json(path, audit.model_dump())
    return str(path)


def resolve_user_id_for_telegram(telegram_user_id: int, full_name: str) -> str:
    for directory in list_user_dirs():
        try:
            profile = UserProfile.model_validate(read_json(directory / "profile.json"))
        except StateFileError:
            continue
        if profile.telegram_user_id == telegram_user_id:
            return profile.user_id

    user_id = f"solo-{telegram_user_id}"
    destination = user_dir(user_id)
    template = user_dir(DEMO_TEMPLATE_USER_ID)
    if template.exists() and not destination.exists():
        shutil.copytree(template, destination)
    else:
        ensure_directory(destination / "course_state")
        ensure_directory(destination / "sessions")
        ensure_directory(destination / "weekly_reviews")
        save_active_courses(user_id, ActiveCourses(active_courses=[]))
    profile = UserProfile(
        user_id=user_id,
        name=full_name or user_id,
        preferences={"default_session_minutes": 25, "tone": "direct"},
        telegram_user_id=telegram_user_id,
    )
    save_user_profile(profile)
    return user_id


def hydrate_course_state_metadata(state: CourseState) -> CourseState:
    try:
        pack = load_course_pack(state.course_id)
    except (FileNotFoundError, StateFileError):
        return state
    topic_map = {topic.id: topic for topic in pack["topics"]}
    for topic in state.topics:
        definition = topic_map.get(topic.id)
        if definition is None:
            continue
        topic.priority_within_course = definition.priority_within_course
        topic.prerequisites = list(definition.prerequisites)
        topic.next_topics = list(definition.next_topics)
        topic.starter = definition.starter
        topic.review_weight = definition.review_weight
        topic.mode_preference = definition.mode_preference
        topic.group = definition.group
    return state
