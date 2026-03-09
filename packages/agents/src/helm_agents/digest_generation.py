from dataclasses import dataclass
from datetime import UTC, datetime
from math import floor

from helm_agents.digest_query import DigestInputs

MAX_DIGEST_ITEMS = 5
MIN_DIGEST_SCORE = 50
FRESHNESS_DECAY_PER_DAY = 3

SOURCE_BASE_SCORE = {
    "action": 65,
    "digest": 55,
    "draft": 50,
    "study": 45,
}


@dataclass(frozen=True)
class RankedDigestItem:
    source_type: str
    source_id: int
    title: str
    action: str
    score: int


def build_digest_text(inputs: DigestInputs, now: datetime | None = None) -> str:
    ranked_items = rank_digest_items(inputs, now=now)
    if not ranked_items:
        return (
            "Daily Brief\n"
            "No urgent items from current artifacts.\n"
            "Next: run /actions for backlog review."
        )

    lines = ["Daily Brief", "Top priorities today:"]
    for index, item in enumerate(ranked_items, start=1):
        lines.append(f"{index}. {item.title} -> {item.action}")
    return "\n".join(lines)


def rank_digest_items(inputs: DigestInputs, now: datetime | None = None) -> list[RankedDigestItem]:
    evaluation_time = _normalize_now(now)
    candidates = [
        *[
            RankedDigestItem(
                source_type="action",
                source_id=item.id,
                title=item.title,
                action=f"Complete action item #{item.id}.",
                score=_score_item(
                    source_type="action",
                    priority=item.priority,
                    created_at=item.created_at,
                    now=evaluation_time,
                ),
            )
            for item in inputs.open_action_items
        ],
        *[
            RankedDigestItem(
                source_type="digest",
                source_id=item.id,
                title=item.title,
                action=f"Review {item.domain} signal and decide next move.",
                score=_score_item(
                    source_type="digest",
                    priority=item.priority,
                    created_at=item.created_at,
                    now=evaluation_time,
                ),
            )
            for item in inputs.top_digest_items
        ],
        *[
            RankedDigestItem(
                source_type="draft",
                source_id=item.id,
                title=f"Pending draft on {item.channel_type}",
                action=f"Approve or edit draft #{item.id}.",
                score=_score_item(
                    source_type="draft",
                    priority=2,
                    created_at=item.created_at,
                    now=evaluation_time,
                ),
            )
            for item in inputs.pending_drafts
        ],
        *[
            RankedDigestItem(
                source_type="study",
                source_id=item.id,
                title=item.title,
                action=f"Do next study block for task #{item.id}.",
                score=_score_item(
                    source_type="study",
                    priority=item.priority,
                    created_at=item.created_at,
                    now=evaluation_time,
                ),
            )
            for item in inputs.study_priorities
        ],
    ]
    filtered = [item for item in candidates if item.score >= MIN_DIGEST_SCORE]
    return sorted(filtered, key=lambda item: item.score, reverse=True)[:MAX_DIGEST_ITEMS]


def _score_item(source_type: str, priority: int, created_at: datetime | None, now: datetime) -> int:
    base_score = SOURCE_BASE_SCORE[source_type]
    priority_score = _priority_to_score(priority)
    age_penalty = _age_penalty(created_at=created_at, now=now)
    return base_score + priority_score - age_penalty


def _priority_to_score(priority: int) -> int:
    normalized = max(1, min(priority, 5))
    return (6 - normalized) * 9


def _age_penalty(created_at: datetime | None, now: datetime) -> int:
    if created_at is None:
        return 0
    created = _to_utc(created_at)
    age_seconds = max(0.0, (now - created).total_seconds())
    age_days = floor(age_seconds / 86400)
    return age_days * FRESHNESS_DECAY_PER_DAY


def _normalize_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(tz=UTC)
    return _to_utc(now)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
