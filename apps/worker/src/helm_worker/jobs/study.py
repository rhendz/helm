from helm_observability.logging import get_logger

logger = get_logger("helm_worker.jobs.study")


def run() -> None:
    logger.info("study_job_tick")
    # TODO(v1-phase4): poll manual study queue and run study workflow.
