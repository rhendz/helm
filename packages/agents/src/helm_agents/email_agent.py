from helm_observability.logging import get_logger


def run_email_triage(message: dict) -> dict:
    logger = get_logger("helm_agents.email")
    logger.info("email_triage_stub", message_id=message.get("id"))
    # TODO(v1-phase2): classify message, create artifacts, and produce draft when needed.
    return {"status": "stub", "message_id": message.get("id")}
