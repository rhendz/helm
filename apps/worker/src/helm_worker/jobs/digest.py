from helm_agents.digest_agent import generate_daily_digest
from helm_observability.logging import get_logger
from helm_telegram_bot.services.digest_delivery import TelegramDigestDeliveryService

logger = get_logger("helm_worker.jobs.digest")
_delivery_service = TelegramDigestDeliveryService()


def run() -> None:
    digest = generate_daily_digest()
    logger.info(
        "digest_job_built",
        preview=digest.text[:120],
        action_count=digest.action_count,
        digest_item_count=digest.digest_item_count,
        pending_draft_count=digest.pending_draft_count,
    )
    try:
        _delivery_service.deliver(digest.text)
    except Exception as exc:  # noqa: BLE001
        logger.error("digest_job_delivery_failed", error=str(exc))
        raise
