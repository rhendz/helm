import time

from helm_observability.agent_runs import record_agent_run
from helm_observability.logging import get_logger, setup_logging

from helm_worker.config import settings
from helm_worker.jobs.registry import JOBS


def run() -> None:
    setup_logging()
    logger = get_logger("helm_worker")

    logger.info("worker_started", poll_seconds=settings.worker_poll_seconds, jobs=list(JOBS))
    while True:
        for name, job in JOBS.items():
            try:
                record_agent_run(
                    agent_name=name,
                    source_type="worker",
                    source_id="scheduler",
                    execute=job,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("worker_job_failed", job=name, error=str(exc))
        time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    run()
