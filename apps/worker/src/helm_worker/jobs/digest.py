from helm_agents.digest_agent import build_daily_digest
from helm_observability.logging import get_logger

logger = get_logger("helm_worker.jobs.digest")


def run() -> None:
    preview = build_daily_digest()
    logger.info("digest_job_tick", preview=preview[:120])
    # TODO(v1-phase3): deliver digest via telegram connector/send API.
