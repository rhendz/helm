from datetime import datetime, timedelta

from helm_agents.digest_agent import generate_daily_digest
from helm_observability.logging import get_logger
from helm_storage.db import SessionLocal
from helm_storage.models import AgentRunORM
from helm_storage.repositories.agent_runs import AgentRunStatus
from helm_telegram_bot.services.digest_delivery import TelegramDigestDeliveryService
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

logger = get_logger("helm_worker.jobs.digest")
_delivery_service = TelegramDigestDeliveryService()
_AUTO_DIGEST_INTERVAL = timedelta(hours=24)


def run() -> None:
    if _auto_delivery_recently_sent():
        logger.info("digest_job_skipped_interval")
        return

    digest = generate_daily_digest()
    linkedin_count = getattr(digest, "linkedin_opportunity_count", 0)
    stale_pending_count = getattr(digest, "stale_pending_draft_count", 0)
    logger.info(
        "digest_job_built",
        preview=digest.text[:120],
        action_count=digest.action_count,
        digest_item_count=digest.digest_item_count,
        linkedin_opportunity_count=linkedin_count,
        pending_draft_count=digest.pending_draft_count,
        stale_pending_draft_count=stale_pending_count,
    )
    total_signals = (
        digest.action_count
        + digest.digest_item_count
        + linkedin_count
        + digest.pending_draft_count
    )
    if total_signals == 0:
        logger.info("digest_job_skipped_empty")
        return
    try:
        _delivery_service.deliver(digest.text)
    except Exception as exc:  # noqa: BLE001
        logger.error("digest_job_delivery_failed", error=str(exc))
        raise


def _auto_delivery_recently_sent() -> bool:
    now = datetime.utcnow()
    try:
        with SessionLocal() as session:
            statement = (
                select(AgentRunORM)
                .where(AgentRunORM.agent_name == "digest")
                .where(AgentRunORM.source_type == "worker")
                .where(AgentRunORM.source_id == "scheduler")
                .where(AgentRunORM.status == AgentRunStatus.SUCCEEDED.value)
                .order_by(AgentRunORM.completed_at.desc(), AgentRunORM.id.desc())
                .limit(1)
            )
            last_run = session.execute(statement).scalars().first()
    except SQLAlchemyError:
        logger.warning("digest_job_interval_check_failed")
        return False

    if last_run is None:
        return False

    last_completed_at = last_run.completed_at
    if last_completed_at is None:
        return False

    return (now - last_completed_at.replace(tzinfo=None)) < _AUTO_DIGEST_INTERVAL
