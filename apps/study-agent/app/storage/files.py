from __future__ import annotations

import json
from pathlib import Path

from app.config import COURSES_DIR, PROMPTS_DIR, USERS_DIR
from app.schemas.course import ActiveCourses, CourseState, UserProfile
from app.schemas.session import ActiveSessionContext, CheckinState, SessionRecord


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict | list) -> None:
    ensure_directory(path.parent)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_markdown(path: Path, content: str) -> None:
    ensure_directory(path.parent)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def load_course_pack(course_id: str) -> dict:
    course_dir = COURSES_DIR / course_id
    return {
        "course": (course_dir / "course.md").read_text(encoding="utf-8"),
        "topics": read_json(course_dir / "topics.json"),
        "rubric": (course_dir / "rubric.md").read_text(encoding="utf-8"),
        "sources": (course_dir / "sources.md").read_text(encoding="utf-8"),
    }


def user_dir(user_id: str) -> Path:
    return USERS_DIR / user_id


def load_user_profile(user_id: str) -> UserProfile:
    return UserProfile.model_validate(read_json(user_dir(user_id) / "profile.json"))


def load_active_courses(user_id: str) -> ActiveCourses:
    return ActiveCourses.model_validate(read_json(user_dir(user_id) / "active_courses.json"))


def load_course_state(user_id: str, course_id: str) -> CourseState:
    path = user_dir(user_id) / "course_state" / f"{course_id}.json"
    return CourseState.model_validate(read_json(path))


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
