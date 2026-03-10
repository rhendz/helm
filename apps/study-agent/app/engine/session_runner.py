from __future__ import annotations

from app.engine.prioritizer import choose_recommendation
from app.engine.rules import (
    activate_session,
    apply_session_abandon,
    expire_session,
    new_session_record,
    now_utc,
    resume_session,
    session_is_expired,
)
from app.schemas.session import ActiveSessionContext, Recommendation, SessionRecord
from app.storage.files import (
    StateFileError,
    clear_active_session,
    list_course_states,
    load_active_session,
    load_course_pack,
    load_course_state,
    load_session_record,
    save_active_session,
    save_course_state,
    save_recommendation_audit,
    save_session_record,
)


def recommend_for_today(user_id: str, *, persist_audit: bool = True) -> Recommendation:
    recommendation = choose_recommendation(list_course_states(user_id))
    if persist_audit and recommendation.audit is not None:
        save_recommendation_audit(user_id, recommendation.audit)
    return recommendation


def start_session(
    user_id: str,
    llm_client,
    action: str | None = None,
) -> tuple[ActiveSessionContext | None, str]:
    now = now_utc()
    existing, existing_record, state_error = _load_active_session_bundle(user_id)
    if state_error:
        clear_active_session(user_id)
        if action == "resume":
            return None, state_error
        context = _create_session(
            user_id,
            llm_client,
            counts_toward_schedule=True,
            recovery_action="recovered_from_corrupt_state",
        )
        return context, f"{state_error} Starting a fresh session."

    if existing is not None:
        if session_is_expired(existing, now):
            existing_record = expire_session(existing_record, now)
            save_session_record(user_id, existing_record)
            clear_active_session(user_id)
            if action == "resume":
                return None, "The previous session expired and cannot be resumed."
            recovery_message = "The previous session expired. Starting a fresh replacement session."
            context = _create_session(
                user_id,
                llm_client,
                counts_toward_schedule=False,
                recovery_action="restart_after_expire",
            )
            return context, recovery_message

        if action == "abandon":
            course = load_course_state(user_id, existing.course_id)
            course, existing_record = apply_session_abandon(
                course,
                existing.topic_id,
                existing_record,
                now=now,
            )
            save_course_state(user_id, course)
            save_session_record(user_id, existing_record)
            clear_active_session(user_id)
            return (
                None,
                f"Abandoned {existing.course_title} / {existing.topic_name}. "
                "Run /start_session to begin again.",
            )

        if action == "restart":
            course = load_course_state(user_id, existing.course_id)
            course, existing_record = apply_session_abandon(
                course,
                existing.topic_id,
                existing_record,
                now=now,
            )
            save_course_state(user_id, course)
            save_session_record(user_id, existing_record)
            clear_active_session(user_id)
            context = _create_session(
                user_id,
                llm_client,
                counts_toward_schedule=False,
                recovery_action="restarted",
            )
            return (
                context,
                "Restarted the previous session without double-counting scheduled adherence.",
            )

        existing_record, existing = resume_session(existing_record, existing, now=now)
        save_session_record(user_id, existing_record)
        save_active_session(user_id, existing)
        return existing, "Resuming your active session."

    context = _create_session(
        user_id,
        llm_client,
        counts_toward_schedule=True,
        recovery_action="fresh",
    )
    return context, "Starting a fresh session."


def validate_active_session(
    user_id: str,
) -> tuple[ActiveSessionContext | None, SessionRecord | None, str | None]:
    now = now_utc()
    active, record, state_error = _load_active_session_bundle(user_id)
    if state_error:
        clear_active_session(user_id)
        return None, None, state_error
    if active is None:
        return None, None, "No active session. Run /start_session first."
    if session_is_expired(active, now):
        record = expire_session(record, now)
        save_session_record(user_id, record)
        clear_active_session(user_id)
        return None, None, "The active session expired. Run /start_session to restart it."

    if record.status != "awaiting_answer":
        return None, None, f"Session is in an invalid state for /answer: {record.status}."

    return active, record, None


def _create_session(
    user_id: str,
    llm_client,
    *,
    counts_toward_schedule: bool,
    recovery_action: str | None,
) -> ActiveSessionContext:
    now = now_utc()
    recommendation = recommend_for_today(user_id, persist_audit=True)
    record = new_session_record(
        user_id,
        recommendation,
        now=now,
        counts_toward_schedule=counts_toward_schedule,
        recovery_action=recovery_action,
    )
    save_session_record(user_id, record)

    course_pack = load_course_pack(recommendation.course_id)
    topic_payload = _build_topic_payload(course_pack, recommendation)
    teaching_text = llm_client.teach_concept(topic_payload)
    quiz_text = llm_client.generate_quiz(topic_payload)
    record, context = activate_session(
        record,
        recommendation,
        teaching_text=teaching_text,
        quiz_text=quiz_text,
        now=now,
    )
    save_session_record(user_id, record)
    save_active_session(user_id, context)
    return context


def _build_topic_payload(course_pack: dict, recommendation: Recommendation) -> str:
    topic = next(topic for topic in course_pack["topics"] if topic.id == recommendation.topic_id)
    return (
        f"Course overview:\n{course_pack['course']}\n\n"
        f"Topic:\n{topic.name}\n{topic.summary}\n\n"
        f"Rubric:\n{course_pack['rubric']}\n\n"
        f"Sources:\n{course_pack['sources']}\n\n"
        f"Policy stage: {recommendation.policy_stage}\n"
        f"Mode: {recommendation.mode}\n"
        f"Reason:\n{recommendation.reason}\n"
    )


def _load_active_session_bundle(
    user_id: str,
) -> tuple[ActiveSessionContext | None, SessionRecord | None, str | None]:
    try:
        active = load_active_session(user_id)
    except (StateFileError, ValueError):
        return None, None, "The active session state is corrupted. It was cleared."
    if active is None:
        return None, None, None
    try:
        record = load_session_record(user_id, active.session_id)
    except (StateFileError, ValueError):
        return None, None, "The session record is missing or corrupted. It was cleared."
    return active, record, None
