from __future__ import annotations

from datetime import date, timedelta

from app.schemas.course import TopicState


def next_review_date(topic: TopicState, score: float | None = None) -> str:
    today = date.today()
    if score is not None and score < 0.45:
        return (today + timedelta(days=1)).isoformat()
    if topic.state == "shaky":
        return (today + timedelta(days=2)).isoformat()
    if topic.state == "learning":
        return (today + timedelta(days=4)).isoformat()
    if topic.state == "solid":
        return (today + timedelta(days=7)).isoformat()
    return (today + timedelta(days=3)).isoformat()
