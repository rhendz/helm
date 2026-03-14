from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from app.schemas.course import CourseState, TopicPerformance, TopicState
from app.schemas.session import (
    Recommendation,
    RecommendationAlternative,
    RecommendationAudit,
    RecommendationBreakdown,
)

POLICY_STAGE_ORDER = ("recovery", "consolidation", "advancement")


@dataclass
class _Candidate:
    course: CourseState
    topic: TopicState
    policy_stage: str
    mode: str
    reason: str
    score: float
    breakdown: RecommendationBreakdown
    winning_factors: list[str]
    blocked_reasons: list[str]


def choose_recommendation(courses: list[CourseState]) -> Recommendation:
    today = date.today()
    candidates = [
        _build_candidate(course, topic, today) for course in courses for topic in course.topics
    ]
    if not candidates:
        raise ValueError("No active course recommendation could be created")

    best = _choose_best_candidate(candidates)
    alternatives = [
        RecommendationAlternative(
            course_id=item.course.course_id,
            topic_id=item.topic.id,
            policy_stage=item.policy_stage,
            score=item.score,
            why_not=_alternative_reason(best, item),
        )
        for item in sorted(candidates, key=lambda candidate: candidate.score, reverse=True)
        if item.topic.id != best.topic.id or item.course.course_id != best.course.course_id
    ][:3]
    created_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    audit = RecommendationAudit(
        created_at=created_at,
        course_id=best.course.course_id,
        course_title=best.course.title,
        topic_id=best.topic.id,
        topic_name=best.topic.name,
        mode=best.mode,
        policy_stage=best.policy_stage,
        reason=best.reason,
        winning_factors=best.winning_factors,
        blocked_reasons=best.blocked_reasons,
        breakdown=best.breakdown,
        alternatives=alternatives,
    )
    return Recommendation(
        course_id=best.course.course_id,
        course_title=best.course.title,
        topic_id=best.topic.id,
        topic_name=best.topic.name,
        mode=best.mode,
        policy_stage=best.policy_stage,
        reason=best.reason,
        score=best.score,
        breakdown=best.breakdown,
        audit=audit,
    )


def _choose_best_candidate(candidates: list[_Candidate]) -> _Candidate:
    if not candidates:
        raise ValueError("No recommendation candidates were produced")
    return max(candidates, key=lambda candidate: candidate.score)


def _build_candidate(course: CourseState, topic: TopicState, today: date) -> _Candidate:
    blocked_reasons = _blocked_reasons(course, topic)
    due_review = _is_due(topic, today)
    cooldown_active = _cooldown_active(topic, today)
    recent_failures = _recent_failures(topic.recent_history)
    recent_stability = _recent_stability(topic.recent_history)
    all_topics_unseen = all(item.last_seen is None for item in course.topics)

    if _should_recover(course, topic, due_review, recent_failures):
        stage = "recovery"
    elif _should_consolidate(topic, due_review, today) or topic.state != "unseen":
        stage = "consolidation"
    else:
        stage = "advancement"

    breakdown = RecommendationBreakdown()
    breakdown.course_priority = float(course.priority * 7)
    breakdown.due_review = 18.0 if due_review else 0.0
    breakdown.recovery_pressure = _recovery_pressure(course, topic, due_review, recent_failures)
    breakdown.consolidation_pressure = _consolidation_pressure(topic, due_review, recent_stability)
    breakdown.advancement_pressure = _advancement_pressure(course, topic, all_topics_unseen)
    breakdown.weak_signal_pressure = float(len(topic.weak_signals) * 1.2)
    breakdown.recent_performance_pressure = _recent_performance_pressure(topic)
    breakdown.miss_pressure = _miss_pressure(course)
    breakdown.pace_pressure = _pace_pressure(course, today)
    breakdown.deadline_pressure = _deadline_pressure(course, today)
    breakdown.starter_bonus = 7.0 if topic.starter and all_topics_unseen else 0.0
    breakdown.progression_bonus = _progression_bonus(course, topic, all_topics_unseen)
    breakdown.review_weight_bonus = round((topic.review_weight - 1.0) * 5, 2)
    breakdown.prerequisite_penalty = 30.0 if blocked_reasons else 0.0
    breakdown.cooldown_penalty = (
        _cooldown_penalty(topic, today, recent_failures) if cooldown_active else 0.0
    )
    if stage == "advancement" and topic.state != "unseen":
        breakdown.cooldown_penalty += 18.0
    if stage == "consolidation" and _ready_to_progress(course, topic):
        breakdown.cooldown_penalty += 14.0
    breakdown.stage_bias = _stage_bias(stage)
    breakdown.total = round(
        breakdown.course_priority
        + breakdown.due_review
        + breakdown.recovery_pressure
        + breakdown.consolidation_pressure
        + breakdown.advancement_pressure
        + breakdown.weak_signal_pressure
        + breakdown.recent_performance_pressure
        + breakdown.miss_pressure
        + breakdown.pace_pressure
        + breakdown.deadline_pressure
        + breakdown.starter_bonus
        + breakdown.progression_bonus
        + breakdown.review_weight_bonus
        + breakdown.stage_bias
        - breakdown.prerequisite_penalty
        - breakdown.cooldown_penalty,
        2,
    )
    mode = _choose_mode(course, topic, stage, recent_failures)
    winning_factors = _winning_factors(topic, breakdown, stage, blocked_reasons)
    reason = _build_reason(course, topic, stage, mode, winning_factors, blocked_reasons)
    return _Candidate(
        course=course,
        topic=topic,
        policy_stage=stage,
        mode=mode,
        reason=reason,
        score=breakdown.total,
        breakdown=breakdown,
        winning_factors=winning_factors,
        blocked_reasons=blocked_reasons,
    )


def _blocked_reasons(course: CourseState, topic: TopicState) -> list[str]:
    if topic.state != "unseen":
        return []
    topic_map = {item.id: item for item in course.topics}
    reasons = []
    for prerequisite in topic.prerequisites:
        dependency = topic_map.get(prerequisite)
        if dependency is None:
            reasons.append(f"missing prerequisite metadata for {prerequisite}")
            continue
        if not _prerequisite_ready(dependency):
            reasons.append(f"prerequisite {dependency.name} is not stable yet")
    return reasons


def _prerequisite_ready(topic: TopicState) -> bool:
    if topic.state == "solid":
        return True
    latest = topic.recent_history[0] if topic.recent_history else None
    if latest is None or latest.score is None:
        return False
    return latest.outcome in {"completed_full", "completed_lite"} and (
        topic.mastery >= 0.65 and latest.score >= 0.75
    )


def _should_recover(
    course: CourseState,
    topic: TopicState,
    due_review: bool,
    recent_failures: int,
) -> bool:
    if recent_failures >= 2:
        return True
    if due_review and topic.state == "shaky":
        return True
    if due_review and (topic.weak_signals or recent_failures >= 1):
        return True
    if course.adherence.miss_streak >= 2 and due_review:
        return True
    return False


def _should_consolidate(topic: TopicState, due_review: bool, today: date) -> bool:
    if topic.state in {"learning", "solid"} and due_review:
        return True
    latest = topic.recent_history[0] if topic.recent_history else None
    if (
        topic.state == "learning"
        and topic.last_seen
        and latest is not None
        and latest.outcome in {"missed", "abandoned", "expired"}
        and not _cooldown_active(topic, today)
    ):
        return True
    if (
        topic.state == "learning"
        and topic.last_seen
        and latest is not None
        and latest.score is not None
        and latest.score < 0.6
        and not _cooldown_active(topic, today)
    ):
        return True
    return False


def _recovery_pressure(
    course: CourseState,
    topic: TopicState,
    due_review: bool,
    recent_failures: int,
) -> float:
    pressure = 0.0
    if due_review:
        pressure += 5.0
    if topic.state == "shaky":
        pressure += 7.0
    pressure += float(recent_failures * 4)
    if course.adherence.miss_streak:
        pressure += float(course.adherence.miss_streak * 2)
    return round(pressure, 2)


def _consolidation_pressure(topic: TopicState, due_review: bool, recent_stability: float) -> float:
    pressure = 0.0
    if topic.state == "learning":
        pressure += 6.0
    elif topic.state == "solid" and due_review:
        pressure += 4.0
    if due_review:
        pressure += 3.0
    if recent_stability:
        pressure += recent_stability
    return round(pressure, 2)


def _advancement_pressure(course: CourseState, topic: TopicState, all_topics_unseen: bool) -> float:
    if topic.state != "unseen":
        return 0.0
    pressure = 4.0
    if all_topics_unseen and topic.starter:
        pressure += 6.0
    pressure += float(topic.priority_within_course)
    if topic.prerequisites:
        pressure += 1.0
    if course.adherence.miss_streak == 0:
        pressure += 1.5
    return round(pressure, 2)


def _progression_bonus(course: CourseState, topic: TopicState, all_topics_unseen: bool) -> float:
    if topic.state != "unseen":
        return 0.0
    if all_topics_unseen and topic.starter:
        return 8.0
    stable_predecessors = 0
    for item in course.topics:
        if topic.id in item.next_topics and (item.state == "solid" or item.mastery >= 0.7):
            stable_predecessors += 1
    return round(stable_predecessors * 4.0 + topic.priority_within_course * 0.8, 2)


def _ready_to_progress(course: CourseState, topic: TopicState) -> bool:
    if topic.state == "unseen" or not topic.next_topics:
        return False
    latest = topic.recent_history[0] if topic.recent_history else None
    if latest is None or latest.score is None or latest.score < 0.8:
        return False
    topic_map = {item.id: item for item in course.topics}
    for next_topic_id in topic.next_topics:
        candidate = topic_map.get(next_topic_id)
        if candidate is not None and not _blocked_reasons(course, candidate):
            return True
    return False


def _recent_performance_pressure(topic: TopicState) -> float:
    pressure = 0.0
    for item in topic.recent_history[:4]:
        if item.outcome in {"missed", "abandoned", "expired"}:
            pressure += 4.0
        elif item.score is not None:
            pressure += max(0.0, (0.72 - item.score) * 7)
        pressure += len(item.weak_signals) * 0.3
    return round(pressure, 2)


def _recent_failures(history: list[TopicPerformance]) -> int:
    failures = 0
    for item in history[:4]:
        if item.outcome in {"missed", "abandoned", "expired"}:
            failures += 1
        elif item.score is not None and item.score < 0.5:
            failures += 1
    return failures


def _recent_stability(history: list[TopicPerformance]) -> float:
    stability = 0.0
    for item in history[:3]:
        if item.score is not None and item.score >= 0.72:
            stability += 1.5
    return round(stability, 2)


def _cooldown_active(topic: TopicState, today: date) -> bool:
    if topic.cooldown_until and date.fromisoformat(topic.cooldown_until) > today:
        return True
    if len(topic.recent_history) < 2:
        return False
    recent = topic.recent_history[:2]
    completed_recent = [
        item
        for item in recent
        if item.outcome in {"completed_full", "completed_lite"} and item.score is not None
    ]
    if len(completed_recent) < 2:
        return False
    return all(item.score >= 0.65 for item in completed_recent)


def _cooldown_penalty(topic: TopicState, today: date, recent_failures: int) -> float:
    if recent_failures:
        return 2.0
    if topic.cooldown_until and date.fromisoformat(topic.cooldown_until) > today:
        days = (date.fromisoformat(topic.cooldown_until) - today).days
        return float(max(3, days * 2))
    return 5.0


def _miss_pressure(course: CourseState) -> float:
    gap = max(
        0,
        course.adherence.missed + course.adherence.abandoned - course.adherence.completed_total,
    )
    return float(course.adherence.miss_streak * 2 + gap)


def _pace_pressure(course: CourseState, today: date) -> float:
    sessions_per_week = int(course.cadence.get("sessions_per_week", 3) or 3)
    target_gap = max(1, round(7 / sessions_per_week))
    if not course.last_session_date:
        return 3.0
    days_since = (today - date.fromisoformat(course.last_session_date)).days
    return float(max(0, days_since - target_gap))


def _deadline_pressure(course: CourseState, today: date) -> float:
    deadline = course.cadence.get("deadline")
    if not deadline:
        return 0.0
    days_left = (date.fromisoformat(deadline) - today).days
    if days_left <= 14:
        return 6.0
    if days_left <= 30:
        return 3.0
    return 0.0


def _stage_bias(stage: str) -> float:
    if stage == "recovery":
        return 12.0
    if stage == "consolidation":
        return 7.0
    return 4.0


def _choose_mode(course: CourseState, topic: TopicState, stage: str, recent_failures: int) -> str:
    if topic.mode_preference == "lite":
        return "lite"
    if topic.mode_preference == "full" and course.adherence.miss_streak == 0:
        return "full"
    if stage == "recovery":
        return "lite"
    if course.adherence.miss_streak >= 2:
        return "lite"
    if recent_failures and topic.mode_preference != "full":
        return "lite"
    if stage == "advancement" and topic.mode_preference != "lite":
        return "full"
    return "full"


def _winning_factors(
    topic: TopicState,
    breakdown: RecommendationBreakdown,
    stage: str,
    blocked_reasons: list[str],
) -> list[str]:
    if blocked_reasons:
        return blocked_reasons[:2]
    stage_names = {
        "recovery": {"recovery pressure", "due review", "recent weak performance", "weak signals"},
        "consolidation": {"consolidation pressure", "due review", "recent weak performance"},
        "advancement": {"advancement pressure", "progression", "starter topic"},
    }
    named_values = [
        ("due review", breakdown.due_review),
        ("recovery pressure", breakdown.recovery_pressure),
        ("consolidation pressure", breakdown.consolidation_pressure),
        ("advancement pressure", breakdown.advancement_pressure),
        ("recent weak performance", breakdown.recent_performance_pressure),
        ("weak signals", breakdown.weak_signal_pressure),
        ("course priority", breakdown.course_priority),
        ("progression", breakdown.progression_bonus),
        ("starter topic", breakdown.starter_bonus),
    ]
    ranked = [
        name
        for name, value in sorted(named_values, key=lambda item: item[1], reverse=True)
        if value > 0
    ]
    preferred = [name for name in ranked if name in stage_names[stage]]
    supporting = [name for name in ranked if name not in stage_names[stage]]
    factors = preferred + supporting
    if stage == "recovery" and topic.weak_signals and "weak signals" not in factors:
        factors.append("weak signals")
    return factors[:3] or ["baseline priority"]


def _build_reason(
    course: CourseState,
    topic: TopicState,
    stage: str,
    mode: str,
    winning_factors: list[str],
    blocked_reasons: list[str],
) -> str:
    if blocked_reasons:
        blocked = "; ".join(blocked_reasons)
        return (
            f"{course.title} / {topic.name} is only considered for advancement after {blocked}. "
            f"Mode is {mode} because prerequisites are still blocking a deeper session."
        )
    detail_text = ", ".join(winning_factors)
    if stage == "recovery":
        stage_text = "recovery"
        mode_text = (
            "a smaller consistency-first session reduces overload while stabilizing weak material"
        )
    elif stage == "consolidation":
        stage_text = "consolidation"
        mode_text = "the topic is stable enough for reinforcement without forcing a restart"
    else:
        stage_text = "advancement"
        mode_text = "the path is clear enough to move forward instead of repeating review"
    if mode == "full" and stage != "recovery":
        mode_text = "recent stability supports a fuller teach-quiz-review loop"
    return (
        f"{course.title} / {topic.name} is next in {stage_text} because of {detail_text}. "
        f"Mode is {mode} because {mode_text}."
    )


def _alternative_reason(best: _Candidate, candidate: _Candidate) -> str:
    if candidate.blocked_reasons:
        blocked = "; ".join(candidate.blocked_reasons)
        return f"Blocked from beating the chosen topic because {blocked}."
    if candidate.policy_stage != best.policy_stage:
        return f"{candidate.policy_stage} ranked behind the chosen {best.policy_stage} path."
    return "Lower score than the chosen topic because it had less pressure and progression support."


def _is_due(topic: TopicState, today: date) -> bool:
    if not topic.next_review:
        return False
    return date.fromisoformat(topic.next_review) <= today
