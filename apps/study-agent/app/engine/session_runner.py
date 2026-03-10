from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.engine.prioritizer import choose_recommendation
from app.schemas.session import ActiveSessionContext, Recommendation, SessionRecord
from app.storage.files import (
    list_course_states,
    load_active_session,
    load_course_pack,
    load_course_state,
    save_active_session,
    save_course_state,
    save_session_record,
)


def recommend_for_today(user_id: str) -> Recommendation:
    return choose_recommendation(list_course_states(user_id))


def start_session(user_id: str, llm_client) -> ActiveSessionContext:
    existing = load_active_session(user_id)
    if existing is not None:
        return existing

    recommendation = recommend_for_today(user_id)
    course_pack = load_course_pack(recommendation.course_id)
    topic_payload = _build_topic_payload(course_pack, recommendation.topic_id, recommendation.mode)
    teaching_text = llm_client.teach_concept(topic_payload)
    quiz_text = llm_client.generate_quiz(topic_payload)
    session_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    context = ActiveSessionContext(
        session_id=session_id,
        user_id=user_id,
        course_id=recommendation.course_id,
        topic_id=recommendation.topic_id,
        topic_name=recommendation.topic_name,
        course_title=recommendation.course_title,
        mode=recommendation.mode,
        teaching_text=teaching_text,
        quiz_text=quiz_text,
        started_at=datetime.now().isoformat(timespec="seconds"),
    )
    record = SessionRecord(
        session_id=session_id,
        course_id=recommendation.course_id,
        topic_id=recommendation.topic_id,
        mode=recommendation.mode,
        status="in_progress",
        started_at=context.started_at,
    )
    course_state = load_course_state(user_id, recommendation.course_id)
    course_state.adherence.scheduled += 1
    save_course_state(user_id, course_state)
    save_active_session(user_id, context)
    save_session_record(user_id, record)
    return context


def _build_topic_payload(course_pack: dict, topic_id: str, mode: str) -> str:
    topic = next(topic for topic in course_pack["topics"] if topic["id"] == topic_id)
    return (
        f"Course overview:\n{course_pack['course']}\n\n"
        f"Topic:\n{topic['name']}\n{topic['summary']}\n\n"
        f"Rubric:\n{course_pack['rubric']}\n\n"
        f"Sources:\n{course_pack['sources']}\n\n"
        f"Mode: {mode}\n"
    )
