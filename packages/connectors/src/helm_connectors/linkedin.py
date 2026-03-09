from helm_observability.logging import get_logger


def pull_new_events() -> list[dict]:
    logger = get_logger("helm_connectors.linkedin")
    logger.info("linkedin_pull_stub")
    # TODO(v1-phase5): implement LinkedIn ingestion if integration path is feasible.
    return []
