from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from helm_observability.logging import get_logger
from helm_storage.db import SessionLocal
from helm_storage.repositories.action_items import SQLAlchemyActionItemRepository
from helm_storage.repositories.digest_items import SQLAlchemyDigestItemRepository
from helm_storage.repositories.draft_replies import SQLAlchemyDraftReplyRepository
from helm_storage.repositories.opportunities import SQLAlchemyOpportunityRepository
from sqlalchemy.exc import SQLAlchemyError


@dataclass(slots=True)
class DigestBuildResult:
    text: str
    action_count: int
    digest_item_count: int
    linkedin_opportunity_count: int
    pending_draft_count: int
    stale_pending_draft_count: int
    ranked_signals: list["RankedDigestSignal"]


@dataclass(slots=True)
class RankedDigestSignal:
    source: str
    title: str
    priority: int
    reasons: dict[str, str]
    score: int


def generate_daily_digest(limit: int = 5) -> DigestBuildResult:
    logger = get_logger("helm_agents.digest")
    try:
        with SessionLocal() as session:
            actions = SQLAlchemyActionItemRepository(session).list_open()[:limit]
            digest_items = SQLAlchemyDigestItemRepository(session).list_ranked(limit=limit)
            linkedin_opportunities = SQLAlchemyOpportunityRepository(session).list_open(limit=limit)
            drafts = SQLAlchemyDraftReplyRepository(session).list_pending()[:limit]
    except SQLAlchemyError:
        logger.warning("digest_query_failed")
        return DigestBuildResult(
            text="Daily Brief\nNo artifact data available yet.",
            action_count=0,
            digest_item_count=0,
            linkedin_opportunity_count=0,
            pending_draft_count=0,
            stale_pending_draft_count=0,
            ranked_signals=[],
        )

    lines: list[str] = ["Daily Brief"]
    if actions:
        lines.append("Actions:")
        lines.extend(
            [f"- P{item.priority} {item.title}" for item in actions]
        )
    ranked_signals = _build_ranked_signals(
        actions=actions,
        digest_items=digest_items,
        linkedin_opportunities=linkedin_opportunities,
        drafts=drafts,
    )
    if ranked_signals:
        lines.append("Priority Signals:")
        lines.extend(_render_ranked_signals(ranked_signals[:limit]))
    if drafts:
        lines.append("Pending Drafts:")
        lines.extend([f"- #{draft.id} ({draft.channel_type}) {draft.status}" for draft in drafts])
    stale_drafts = _stale_pending_drafts(drafts=drafts, stale_after_hours=72)
    if stale_drafts:
        lines.append("Stale Approvals:")
        lines.append(
            "- "
            f"{len(stale_drafts)} stale draft(s): "
            + ", ".join(f"#{draft.id}" for draft in stale_drafts[:5])
        )
    if len(lines) == 1:
        lines.append("No open actions, priority signals, or pending drafts.")

    text = "\n".join(lines)
    logger.info(
        "digest_built",
        actions=len(actions),
        digest_items=len(digest_items),
        linkedin_opportunities=len(linkedin_opportunities),
        drafts=len(drafts),
    )
    return DigestBuildResult(
        text=text,
        action_count=len(actions),
        digest_item_count=len(digest_items),
        linkedin_opportunity_count=len(linkedin_opportunities),
        pending_draft_count=len(drafts),
        stale_pending_draft_count=len(stale_drafts),
        ranked_signals=ranked_signals[:limit],
    )


def build_daily_digest() -> str:
    return generate_daily_digest().text


def _build_ranked_signals(
    *,
    actions: list[object],
    digest_items: list[object],
    linkedin_opportunities: list[object],
    drafts: list[object],
) -> list[RankedDigestSignal]:
    signals: list[RankedDigestSignal] = []
    for item in digest_items:
        priority = int(getattr(item, "priority", 3) or 3)
        source = str(getattr(item, "domain", "digest"))
        title = str(getattr(item, "title", "Digest signal"))
        signals.append(
            _build_signal(
                source=source,
                title=title,
                priority=priority,
                created_at=getattr(item, "created_at", None),
            )
        )
    for item in actions:
        priority = int(getattr(item, "priority", 3) or 3)
        title = str(getattr(item, "title", "Action required"))
        signals.append(
            _build_signal(
                source="action",
                title=title,
                priority=priority,
                created_at=getattr(item, "created_at", None),
            )
        )
    for item in linkedin_opportunities:
        priority_score = int(getattr(item, "priority_score", 50) or 50)
        priority = 1 if priority_score >= 80 else 2 if priority_score >= 60 else 3
        role_title = getattr(item, "role_title", "LinkedIn conversation follow-up")
        company = getattr(item, "company", "(unknown)")
        title = f"{role_title} @ {company}"
        signals.append(
            _build_signal(
                source="linkedin",
                title=title,
                priority=priority,
                created_at=getattr(item, "created_at", None),
            )
        )
    for item in drafts:
        status = str(getattr(item, "status", "pending"))
        if status != "pending":
            continue
        title = (
            f"Draft #{getattr(item, 'id', '?')} "
            f"({getattr(item, 'channel_type', 'unknown')})"
        )
        signals.append(
            _build_signal(
                source="draft",
                title=title,
                priority=2,
                created_at=(
                    getattr(item, "updated_at", None)
                    if getattr(item, "updated_at", None) is not None
                    else getattr(item, "created_at", None)
                ),
            )
        )
    return sorted(signals, key=lambda signal: (-signal.score, signal.title.lower()))


def _build_signal(
    *,
    source: str,
    title: str,
    priority: int,
    created_at: object,
) -> RankedDigestSignal:
    urgency = _urgency_label(priority)
    freshness = _freshness_label(created_at)
    reasons = {"source": source, "urgency": urgency, "freshness": freshness}
    score = _score(priority=priority, freshness=freshness)
    return RankedDigestSignal(
        source=source,
        title=title,
        priority=priority,
        reasons=reasons,
        score=score,
    )


def _render_ranked_signals(signals: list[RankedDigestSignal]) -> list[str]:
    return [
        (
            f"- P{signal.priority} [{signal.source}] {signal.title} "
            f"({signal.reasons['urgency']}, {signal.reasons['freshness']})"
        )
        for signal in signals
    ]


def _urgency_label(priority: int) -> str:
    if priority <= 1:
        return "high-urgency"
    if priority == 2:
        return "medium-urgency"
    return "low-urgency"


def _freshness_label(created_at: object) -> str:
    normalized = _normalize_datetime(created_at)
    if normalized is None:
        return "unknown-freshness"
    age = datetime.now(UTC) - normalized
    if age.total_seconds() <= 6 * 60 * 60:
        return "new"
    if age.total_seconds() <= 48 * 60 * 60:
        return "recent"
    return "stale"


def _normalize_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    return None


def _score(*, priority: int, freshness: str) -> int:
    urgency_score = {1: 90, 2: 70}.get(priority, 50)
    freshness_score = {"new": 12, "recent": 6, "stale": 0, "unknown-freshness": 2}[freshness]
    return urgency_score + freshness_score


def _stale_pending_drafts(*, drafts: list[object], stale_after_hours: int) -> list[object]:
    cutoff = datetime.now(UTC) - timedelta(hours=stale_after_hours)
    stale: list[object] = []
    for draft in drafts:
        status = str(getattr(draft, "status", ""))
        if status not in {"pending", "snoozed"}:
            continue
        updated_at = _normalize_datetime(getattr(draft, "updated_at", None))
        if updated_at is None:
            updated_at = _normalize_datetime(getattr(draft, "created_at", None))
        if updated_at is not None and updated_at <= cutoff:
            stale.append(draft)
    return stale
