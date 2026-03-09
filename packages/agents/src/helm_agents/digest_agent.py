from helm_observability.logging import get_logger


def build_daily_digest() -> str:
    logger = get_logger("helm_agents.digest")
    logger.info("build_daily_digest_stub")
    # TODO(v1-phase3): rank artifacts and generate concise actionable briefing.
    return "Daily digest not implemented yet."
