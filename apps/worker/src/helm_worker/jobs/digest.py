from helm_agents.digest_agent import generate_daily_digest
from helm_observability.logging import get_logger
from helm_telegram_bot.services.digest_delivery import TelegramDigestDeliveryService

logger = get_logger("helm_worker.jobs.digest")
_delivery_service = TelegramDigestDeliveryService()


def run() -> None:
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
