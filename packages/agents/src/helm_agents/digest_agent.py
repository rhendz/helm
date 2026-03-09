from dataclasses import dataclass

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
        )

    lines: list[str] = ["Daily Brief"]
    if actions:
        lines.append("Actions:")
        lines.extend(
            [f"- P{item.priority} {item.title}" for item in actions]
        )
    priority_signals: list[str] = [
        f"- P{item.priority} [{item.domain}] {item.title}" for item in digest_items
    ]
    priority_signals.extend(_format_linkedin_opportunity(item) for item in linkedin_opportunities)
    if priority_signals:
        lines.append("Priority Signals:")
        lines.extend(priority_signals[:limit])
    if drafts:
        lines.append("Pending Drafts:")
        lines.extend([f"- #{draft.id} ({draft.channel_type}) {draft.status}" for draft in drafts])
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
    )


def build_daily_digest() -> str:
    return generate_daily_digest().text


def _format_linkedin_opportunity(item: object) -> str:
    title = getattr(item, "role_title", "LinkedIn conversation follow-up")
    company = getattr(item, "company", "(unknown)")
    priority_score = int(getattr(item, "priority_score", 50) or 50)
    priority = 1 if priority_score >= 80 else 2 if priority_score >= 60 else 3
    return f"- P{priority} [linkedin] {title} @ {company}"
