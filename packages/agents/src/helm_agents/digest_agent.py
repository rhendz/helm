from dataclasses import dataclass

from helm_observability.logging import get_logger
from helm_storage.db import SessionLocal
from helm_storage.repositories.action_items import SQLAlchemyActionItemRepository
from helm_storage.repositories.digest_items import SQLAlchemyDigestItemRepository
from helm_storage.repositories.draft_replies import SQLAlchemyDraftReplyRepository
from sqlalchemy.exc import SQLAlchemyError


@dataclass(slots=True)
class DigestBuildResult:
    text: str
    action_count: int
    digest_item_count: int
    pending_draft_count: int


def generate_daily_digest(limit: int = 5) -> DigestBuildResult:
    logger = get_logger("helm_agents.digest")
    try:
        with SessionLocal() as session:
            actions = SQLAlchemyActionItemRepository(session).list_open()[:limit]
            digest_items = SQLAlchemyDigestItemRepository(session).list_ranked(limit=limit)
            drafts = SQLAlchemyDraftReplyRepository(session).list_pending()[:limit]
    except SQLAlchemyError:
        logger.warning("digest_query_failed")
        return DigestBuildResult(
            text="Daily Brief\nNo artifact data available yet.",
            action_count=0,
            digest_item_count=0,
            pending_draft_count=0,
        )

    lines: list[str] = ["Daily Brief"]
    if actions:
        lines.append("Actions:")
        lines.extend(
            [f"- P{item.priority} {item.title}" for item in actions]
        )
    if digest_items:
        lines.append("Priority Signals:")
        lines.extend(
            [f"- P{item.priority} [{item.domain}] {item.title}" for item in digest_items]
        )
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
        drafts=len(drafts),
    )
    return DigestBuildResult(
        text=text,
        action_count=len(actions),
        digest_item_count=len(digest_items),
        pending_draft_count=len(drafts),
    )


def build_daily_digest() -> str:
    return generate_daily_digest().text
