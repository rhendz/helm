from __future__ import annotations

from datetime import date

from app.engine.artifact_writer import write_weekly_checkin_artifact
from app.engine.rules import apply_checkin_proposals, build_checkin_proposals, now_utc
from app.schemas.session import CheckinState
from app.storage.files import (
    StateFileError,
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
    try:
        existing = load_active_checkin(user_id)
    except (StateFileError, ValueError):
        clear_active_checkin(user_id)
        existing = None
    if existing:
        return existing
    state = CheckinState(
        user_id=user_id,
        started_at=now_utc().isoformat(),
        status="collecting",
        current_index=0,
        questions=CHECKIN_QUESTIONS,
        answers=[],
        proposed_changes=[],
        summary=None,
    )
    save_active_checkin(user_id, state)
    return state


def answer_checkin(user_id: str, answer: str, llm_client) -> tuple[bool, str]:
    try:
        state = load_active_checkin(user_id)
    except (StateFileError, ValueError):
        clear_active_checkin(user_id)
        state = None
    if state is None:
        state = start_checkin(user_id)
        return False, state.questions[0]

    if state.status == "awaiting_approval":
        lowered = answer.strip().lower()
        if lowered == "apply":
            return True, apply_checkin_changes(user_id)
        if lowered == "cancel":
            clear_active_checkin(user_id)
            return True, "Weekly check-in canceled. No state changes were applied."
        return (
            False,
            "Reply with /checkin apply to persist changes or /checkin cancel to discard them.",
        )

    state.answers.append(answer.strip())
    state.current_index += 1
    if state.current_index < len(state.questions):
        save_active_checkin(user_id, state)
        return False, state.questions[state.current_index]

    courses = list_course_states(user_id)
    complaint, reprioritization, mastery_fix, cadence_note = state.answers
    proposals = build_checkin_proposals(
        courses,
        reprioritization=reprioritization,
        mastery_fix=mastery_fix,
        cadence_note=cadence_note,
    )
    adherence_summary = _build_adherence_summary(courses)
    summary = llm_client.run_checkin_summary(
        f"Adherence summary:\n{adherence_summary}\n\n"
        f"Complaint:\n{complaint}\n\n"
        f"Reprioritization:\n{reprioritization}\n\n"
        f"Mastery correction:\n{mastery_fix}\n\n"
        f"Cadence note:\n{cadence_note}\n"
    )
    state.status = "awaiting_approval"
    state.summary = summary
    state.proposed_changes = proposals
    save_active_checkin(user_id, state)
    return False, _render_pending_checkin(summary, proposals)


def apply_checkin_changes(user_id: str) -> str:
    try:
        state = load_active_checkin(user_id)
    except (StateFileError, ValueError):
        clear_active_checkin(user_id)
        state = None
    if state is None or state.status != "awaiting_approval":
        return "No pending weekly check-in changes to apply."

    courses = list_course_states(user_id)
    for course in courses:
        updated = apply_checkin_proposals(course, state.proposed_changes)
        save_course_state(user_id, updated)

    adherence_summary = _build_adherence_summary(courses)
    iso_year, iso_week, _ = date.today().isocalendar()
    iso_week_label = f"{iso_year}-W{iso_week:02d}"
    path = write_weekly_checkin_artifact(
        user_id=user_id,
        iso_week=iso_week_label,
        adherence_summary=adherence_summary,
        complaints=state.answers[0],
        reprioritization=state.answers[1],
        mastery_corrections=state.answers[2],
        cadence_notes=state.answers[3],
        next_week_focus=state.summary or "No summary generated.",
    )
    clear_active_checkin(user_id)
    return (
        f"Weekly check-in saved.\nArtifact: {path}\n\nApplied changes:\n"
        f"{_render_changes(state.proposed_changes)}"
    )


def _build_adherence_summary(courses: list) -> str:
    lines = []
    for course in courses:
        lines.append(
            f"{course.title}: scheduled {course.adherence.scheduled}, "
            f"full {course.adherence.completed_full}, lite {course.adherence.completed_lite}, "
            f"missed {course.adherence.missed}, abandoned {course.adherence.abandoned}, "
            f"miss streak {course.adherence.miss_streak}."
        )
    return "\n".join(lines)


def _render_pending_checkin(summary: str, proposals: list) -> str:
    return (
        "Weekly check-in summary:\n"
        f"{summary}\n\n"
        "Proposed changes:\n"
        f"{_render_changes(proposals)}\n\n"
        "Reply with /checkin apply to persist these changes or /checkin cancel to discard them."
    )


def _render_changes(proposals: list) -> str:
    if not proposals:
        return "- No state changes proposed."
    return "\n".join(
        f"- {proposal.course_id}: {proposal.field_path} "
        f"{proposal.old_value} -> {proposal.new_value} "
        f"({proposal.reason})"
        for proposal in proposals
    )
