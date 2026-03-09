from helm_observability.logging import get_logger


def pull_new_messages() -> list[dict]:
    logger = get_logger("helm_connectors.gmail")
    logger.info("gmail_pull_stub")
    # TODO(v1-phase2): implement Gmail ingest path and normalization.
    return []
