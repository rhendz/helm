from __future__ import annotations

from datetime import date, datetime

from app.engine.artifact_writer import write_weekly_checkin_artifact
from app.schemas.session import CheckinState
from app.storage.files import (
    clear_active_checkin,
    list_course_states,
    load_active_checkin,
    save_active_checkin,
    save_course_state,
)

CHECKIN_QUESTIONS = [
    "What is the main complaint with your study system this week?",
    "Which course should be prioritized more or less next week, and why?",
    "Which topic state is wrong right now because it feels easier or shakier than the JSON says?",
    "Is your current cadence realistic, or do you need to adjust it?",
]


def start_checkin(user_id: str) -> CheckinState:
    existing = load_active_checkin(user_id)
    if existing:
        return existing
    state = CheckinState(
        user_id=user_id,
        started_at=datetime.now().isoformat(timespec="seconds"),
        current_index=0,
        questions=CHECKIN_QUESTIONS,
        answers=[],
    )
    save_active_checkin(user_id, state)
    return state


def answer_checkin(user_id: str, answer: str, llm_client) -> tuple[bool, str]:
    state = load_active_checkin(user_id)
    if state is None:
        state = start_checkin(user_id)
        return False, state.questions[0]

    state.answers.append(answer.strip())
    state.current_index += 1
    if state.current_index < len(state.questions):
        save_active_checkin(user_id, state)
        return False, state.questions[state.current_index]

    result = _finalize_checkin(user_id, state, llm_client)
    clear_active_checkin(user_id)
    return True, result


def _finalize_checkin(user_id: str, state: CheckinState, llm_client) -> str:
    courses = list_course_states(user_id)
    complaint, reprioritization, mastery_fix, cadence_note = state.answers
    for course in courses:
        lowered = reprioritization.lower()
        if course.course_id.replace("-", " ") in lowered or course.title.lower() in lowered:
            if any(token in lowered for token in ("more", "higher", "prioritize", "focus")):
                course.priority = min(5, course.priority + 1)
            if any(token in lowered for token in ("less", "lower", "deprioritize")):
                course.priority = max(1, course.priority - 1)
        if any(token in cadence_note.lower() for token in ("too much", "unrealistic", "reduce")):
            current = int(course.cadence.get("sessions_per_week", 3))
            course.cadence["sessions_per_week"] = max(1, current - 1)
        if any(token in cadence_note.lower() for token in ("more", "increase", "push")):
            current = int(course.cadence.get("sessions_per_week", 3))
            course.cadence["sessions_per_week"] = current + 1
        course.weekly_checkin_needed = False
        save_course_state(user_id, course)

    adherence_summary = _build_adherence_summary(courses)
    llm_summary = llm_client.run_checkin_summary(
        f"Adherence summary:\n{adherence_summary}\n\n"
        f"Complaint:\n{complaint}\n\n"
        f"Reprioritization:\n{reprioritization}\n\n"
        f"Mastery correction:\n{mastery_fix}\n\n"
        f"Cadence note:\n{cadence_note}\n"
    )
    iso_year, iso_week, _ = date.today().isocalendar()
    iso_week_label = f"{iso_year}-W{iso_week:02d}"
    path = write_weekly_checkin_artifact(
        user_id=user_id,
        iso_week=iso_week_label,
        adherence_summary=adherence_summary,
        complaints=complaint,
        reprioritization=reprioritization,
        mastery_corrections=mastery_fix,
        cadence_notes=cadence_note,
        next_week_focus=llm_summary,
    )
    return f"Weekly check-in saved.\nArtifact: {path}\n\nNext-week focus:\n{llm_summary}"


def _build_adherence_summary(courses: list) -> str:
    lines = []
    for course in courses:
        lines.append(
            f"{course.title}: completed {course.adherence.completed}/{course.adherence.scheduled}, "
            f"missed {course.adherence.missed}, miss streak {course.adherence.miss_streak}."
        )
    return "\n".join(lines)
