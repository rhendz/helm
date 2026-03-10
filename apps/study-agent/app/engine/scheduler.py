from __future__ import annotations

from datetime import datetime, timedelta

from app.schemas.course import TopicPerformance, TopicState


def next_review_plan(
    topic: TopicState,
    *,
    score: float | None,
    mode: str,
    now: datetime,
) -> tuple[str, str | None]:
    recent_failures = _recent_failures(topic.recent_history)
    recent_strong = _recent_strong_completions(topic.recent_history)

    if score is None:
        days = 1
        cooldown_until = None
    elif score < 0.4 or recent_failures >= 2:
        days = 1
        cooldown_until = None
    elif score < 0.6 or topic.state == "shaky":
        days = 2
        cooldown_until = None
    elif recent_strong >= 2 and score >= 0.75:
        days = 6 if mode == "full" else 4
        cooldown_until = (now.date() + timedelta(days=2)).isoformat()
    elif topic.state == "solid" and score >= 0.8:
        days = 7
        cooldown_until = (now.date() + timedelta(days=2)).isoformat()
    else:
        days = 4 if mode == "full" else 3
        cooldown_until = None
    return (now.date() + timedelta(days=days)).isoformat(), cooldown_until


def _recent_failures(history: list[TopicPerformance]) -> int:
    failures = 0
    for item in history[:4]:
        if item.outcome in {"missed", "abandoned", "expired"}:
            failures += 1
        elif item.score is not None and item.score < 0.5:
            failures += 1
    return failures


def _recent_strong_completions(history: list[TopicPerformance]) -> int:
    strong = 0
    for item in history[:3]:
        if (
            item.outcome in {"completed_full", "completed_lite"}
            and item.score is not None
            and item.score >= 0.75
        ):
            strong += 1
    return strong
