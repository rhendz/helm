from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.engine.scheduler import next_review_plan
from app.schemas.course import CourseState, TopicPerformance
from app.schemas.session import (
    ActiveSessionContext,
    CheckinProposedChange,
    Recommendation,
    ReviewResult,
    SessionRecord,
)

SESSION_TTL_HOURS = 8
RECENT_HISTORY_LIMIT = 5


def now_utc() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def isoformat(value: datetime) -> str:
    return value.isoformat()


def session_expiry(now: datetime) -> str:
    return isoformat(now + timedelta(hours=SESSION_TTL_HOURS))


def new_session_record(
    user_id: str,
    recommendation: Recommendation,
    *,
    now: datetime,
    counts_toward_schedule: bool,
    recovery_action: str | None,
) -> SessionRecord:
    session_id = f"{now.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    return SessionRecord(
        session_id=session_id,
        user_id=user_id,
        course_id=recommendation.course_id,
        topic_id=recommendation.topic_id,
        mode=recommendation.mode,
        policy_stage=recommendation.policy_stage,
        recommendation_reason=recommendation.reason,
        recommendation_breakdown=recommendation.breakdown,
        status="recommended",
        started_at=isoformat(now),
        last_event_at=isoformat(now),
        expires_at=session_expiry(now),
        counts_toward_schedule=counts_toward_schedule,
        recovery_action=recovery_action,
    )


def activate_session(
    record: SessionRecord,
    recommendation: Recommendation,
    *,
    teaching_text: str,
    quiz_text: str,
    now: datetime,
) -> tuple[SessionRecord, ActiveSessionContext]:
    record.status = "in_progress"
    record.last_event_at = isoformat(now)
    record.status = "awaiting_answer"
    record.last_event_at = isoformat(now)
    context = ActiveSessionContext(
        session_id=record.session_id,
        user_id=record.user_id,
        course_id=record.course_id,
        topic_id=record.topic_id,
        topic_name=recommendation.topic_name,
        course_title=recommendation.course_title,
        mode=record.mode,
        status=record.status,
        started_at=record.started_at,
        expires_at=record.expires_at or session_expiry(now),
        policy_stage=recommendation.policy_stage,
        teaching_text=teaching_text,
        quiz_text=quiz_text,
        reason=recommendation.reason,
        breakdown=recommendation.breakdown,
        counts_toward_schedule=record.counts_toward_schedule,
        recovery_action=record.recovery_action,
        resume_count=record.resume_count,
    )
    return record, context


def session_is_expired(session: ActiveSessionContext | SessionRecord, now: datetime) -> bool:
    if not session.expires_at:
        return False
    return datetime.fromisoformat(session.expires_at) <= now


def expire_session(record: SessionRecord, now: datetime) -> SessionRecord:
    record.status = "expired"
    record.last_event_at = isoformat(now)
    return record


def resume_session(
    record: SessionRecord,
    context: ActiveSessionContext,
    *,
    now: datetime,
) -> tuple[SessionRecord, ActiveSessionContext]:
    record.resume_count += 1
    record.recovery_action = "resumed"
    record.last_event_at = isoformat(now)
    record.expires_at = session_expiry(now)
    context.resume_count = record.resume_count
    context.recovery_action = "resumed"
    context.expires_at = record.expires_at
    return record, context


def abandon_session(record: SessionRecord, now: datetime) -> SessionRecord:
    record.status = "abandoned"
    record.last_event_at = isoformat(now)
    record.completed_at = isoformat(now)
    return record


def apply_session_completion(
    course: CourseState,
    topic_id: str,
    session: SessionRecord,
    review: ReviewResult,
    *,
    now: datetime,
) -> tuple[CourseState, SessionRecord]:
    topic = next(topic for topic in course.topics if topic.id == topic_id)
    mastery_delta = _mastery_delta(review.score, session.mode)
    topic.mastery = max(0.0, min(1.0, topic.mastery + mastery_delta))
    topic.last_seen = now.date().isoformat()
    topic.weak_signals = _update_weak_signals(
        topic.weak_signals,
        review.weak_signals,
        review.score,
    )
    topic.state = _derive_topic_state(topic.mastery, review.score)
    topic.next_review, topic.cooldown_until = next_review_plan(
        topic,
        score=review.score,
        mode=session.mode,
        now=now,
    )
    topic.confidence = _confidence_from_score(review.score, len(review.weak_signals))
    topic.recent_history = _prepend_history(
        topic.recent_history,
        TopicPerformance(
            date=now.date().isoformat(),
            mode=session.mode,
            score=round(review.score, 2),
            weak_signals=review.weak_signals,
            outcome="completed_full" if session.mode == "full" else "completed_lite",
        ),
    )

    if session.counts_toward_schedule:
        course.adherence.scheduled += 1
    if session.mode == "full":
        course.adherence.completed_full += 1
    else:
        course.adherence.completed_lite += 1
    course.adherence.miss_streak = 0
    course.last_session_date = now.date().isoformat()

    session.status = "completed"
    session.completed_at = isoformat(now)
    session.last_event_at = isoformat(now)
    session.quiz_score = round(review.score, 2)
    session.review_summary = review.what_was_missing
    session.weak_signals = review.weak_signals
    session.next_step = review.next_step
    return course, session


def apply_session_abandon(
    course: CourseState,
    topic_id: str,
    session: SessionRecord,
    *,
    now: datetime,
) -> tuple[CourseState, SessionRecord]:
    topic = next(topic for topic in course.topics if topic.id == topic_id)
    topic.next_review = (now.date() + timedelta(days=1)).isoformat()
    topic.cooldown_until = None
    topic.recent_history = _prepend_history(
        topic.recent_history,
        TopicPerformance(
            date=now.date().isoformat(),
            mode=session.mode,
            score=None,
            weak_signals=[],
            outcome="abandoned",
        ),
    )
    if session.counts_toward_schedule:
        course.adherence.scheduled += 1
    course.adherence.abandoned += 1
    session = abandon_session(session, now)
    return course, session


def apply_miss(
    course: CourseState,
    topic_id: str,
    reason: str,
    *,
    now: datetime,
) -> CourseState:
    topic = next(topic for topic in course.topics if topic.id == topic_id)
    course.adherence.scheduled += 1
    course.adherence.missed += 1
    course.adherence.miss_streak += 1
    course.adherence.recent_miss_reasons.append(reason)
    course.adherence.recent_miss_reasons = course.adherence.recent_miss_reasons[-5:]
    topic.next_review = (now.date() + timedelta(days=1)).isoformat()
    topic.cooldown_until = None
    topic.recent_history = _prepend_history(
        topic.recent_history,
        TopicPerformance(
            date=now.date().isoformat(),
            mode="lite",
            score=0.25,
            weak_signals=list(topic.weak_signals[:2]),
            outcome="missed",
        ),
    )
    return course


def build_checkin_proposals(
    courses: list[CourseState],
    *,
    reprioritization: str,
    mastery_fix: str,
    cadence_note: str,
) -> list[CheckinProposedChange]:
    proposals: list[CheckinProposedChange] = []
    reprioritization_lower = reprioritization.lower()
    cadence_lower = cadence_note.lower()
    mastery_lower = mastery_fix.lower()

    for course in courses:
        sentiment = _course_reprioritization_signal(reprioritization_lower, course)
        if sentiment > 0:
                new_priority = min(5, course.priority + 1)
                if new_priority != course.priority:
                    proposals.append(
                        CheckinProposedChange(
                            course_id=course.course_id,
                            field_path="priority",
                            old_value=str(course.priority),
                            new_value=str(new_priority),
                            reason="Reprioritization answer raised this course.",
                        )
                    )
        elif sentiment < 0:
                new_priority = max(1, course.priority - 1)
                if new_priority != course.priority:
                    proposals.append(
                        CheckinProposedChange(
                            course_id=course.course_id,
                            field_path="priority",
                            old_value=str(course.priority),
                            new_value=str(new_priority),
                            reason="Reprioritization answer lowered this course.",
                        )
                    )

        current_sessions = int(course.cadence.get("sessions_per_week", 3))
        if any(token in cadence_lower for token in ("too much", "unrealistic", "reduce")):
            new_sessions = max(1, current_sessions - 1)
            if new_sessions != current_sessions:
                proposals.append(
                    CheckinProposedChange(
                        course_id=course.course_id,
                        field_path="cadence.sessions_per_week",
                        old_value=str(current_sessions),
                        new_value=str(new_sessions),
                        reason="Cadence note requested a lower weekly load.",
                    )
                )
        if any(token in cadence_lower for token in ("more", "increase", "push")):
            new_sessions = current_sessions + 1
            if new_sessions != current_sessions:
                proposals.append(
                    CheckinProposedChange(
                        course_id=course.course_id,
                        field_path="cadence.sessions_per_week",
                        old_value=str(current_sessions),
                        new_value=str(new_sessions),
                        reason="Cadence note requested a higher weekly load.",
                    )
                )

        for topic in course.topics:
            if topic.id.replace("-", " ") in mastery_lower or topic.name.lower() in mastery_lower:
                if "shaky" in mastery_lower:
                    proposals.append(
                        CheckinProposedChange(
                            course_id=course.course_id,
                            field_path=f"topics.{topic.id}.state",
                            old_value=topic.state,
                            new_value="shaky",
                            reason="Mastery correction marked this topic shakier than stored.",
                        )
                    )
                elif "solid" in mastery_lower or "easy" in mastery_lower:
                    proposals.append(
                        CheckinProposedChange(
                            course_id=course.course_id,
                            field_path=f"topics.{topic.id}.state",
                            old_value=topic.state,
                            new_value="solid",
                            reason="Mastery correction marked this topic stronger than stored.",
                        )
                    )
                elif "learning" in mastery_lower:
                    proposals.append(
                        CheckinProposedChange(
                            course_id=course.course_id,
                            field_path=f"topics.{topic.id}.state",
                            old_value=topic.state,
                            new_value="learning",
                            reason="Mastery correction moved this topic to learning.",
                        )
                    )
    return _dedupe_proposals(proposals)


def apply_checkin_proposals(
    course: CourseState,
    proposals: list[CheckinProposedChange],
) -> CourseState:
    for proposal in proposals:
        if proposal.course_id != course.course_id:
            continue
        if proposal.field_path == "priority":
            course.priority = int(proposal.new_value)
        elif proposal.field_path == "cadence.sessions_per_week":
            course.cadence["sessions_per_week"] = int(proposal.new_value)
        elif proposal.field_path.startswith("topics.") and proposal.field_path.endswith(".state"):
            topic_id = proposal.field_path.split(".")[1]
            topic = next(topic for topic in course.topics if topic.id == topic_id)
            topic.state = proposal.new_value
            if proposal.new_value == "shaky":
                topic.mastery = min(topic.mastery, 0.4)
                topic.confidence = "low"
            elif proposal.new_value == "learning":
                topic.mastery = min(max(topic.mastery, 0.45), 0.7)
                topic.confidence = "medium"
            elif proposal.new_value == "solid":
                topic.mastery = max(topic.mastery, 0.75)
                topic.confidence = "high"
        course.weekly_checkin_needed = False
    return course


def _mastery_delta(score: float, mode: str) -> float:
    if score >= 0.8:
        base = 0.14
    elif score >= 0.6:
        base = 0.08
    elif score >= 0.4:
        base = 0.02
    else:
        base = -0.05
    return round(base * (1.0 if mode == "full" else 0.65), 3)


def _derive_topic_state(mastery: float, score: float) -> str:
    if mastery >= 0.8 and score >= 0.75:
        return "solid"
    if mastery < 0.45 or score < 0.45:
        return "shaky"
    return "learning"


def _confidence_from_score(score: float, weak_count: int) -> str:
    if score >= 0.8 and weak_count <= 1:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def _merge_signals(existing: list[str], new_signals: list[str]) -> list[str]:
    merged = list(existing)
    for signal in new_signals:
        if signal not in merged:
            merged.append(signal)
    return merged[:8]


def _update_weak_signals(existing: list[str], new_signals: list[str], score: float) -> list[str]:
    if score >= 0.8 and not new_signals:
        return []
    if score >= 0.7:
        return _merge_signals([signal for signal in existing if signal in new_signals], new_signals)
    return _merge_signals(existing, new_signals)


def _prepend_history(
    existing: list[TopicPerformance],
    item: TopicPerformance,
) -> list[TopicPerformance]:
    return [item, *existing][:RECENT_HISTORY_LIMIT]


def _dedupe_proposals(proposals: list[CheckinProposedChange]) -> list[CheckinProposedChange]:
    seen: set[tuple[str, str]] = set()
    deduped: list[CheckinProposedChange] = []
    for proposal in proposals:
        key = (proposal.course_id, proposal.field_path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(proposal)
    return deduped


def _course_reprioritization_signal(text: str, course: CourseState) -> int:
    tokens = [course.course_id.replace("-", " "), course.title.lower()]
    signal = 0
    for token in tokens:
        if token not in text:
            continue
        index = text.find(token)
        window = text[max(0, index - 25) : index + len(token) + 25]
        positive_distance = _nearest_keyword_distance(
            window,
            token,
            ("more", "higher", "prioritize", "focus"),
        )
        negative_distance = _nearest_keyword_distance(
            window,
            token,
            ("less", "lower", "deprioritize"),
        )
        if positive_distance is None and negative_distance is None:
            continue
        if negative_distance is None or (
            positive_distance is not None and positive_distance <= negative_distance
        ):
            signal = max(signal, 1)
        else:
            signal = min(signal, -1)
    return signal


def _nearest_keyword_distance(
    window: str,
    token: str,
    keywords: tuple[str, ...],
) -> int | None:
    token_index = window.find(token)
    distances = []
    for keyword in keywords:
        keyword_index = window.find(keyword)
        if keyword_index != -1:
            distances.append(abs(keyword_index - token_index))
    return min(distances) if distances else None
