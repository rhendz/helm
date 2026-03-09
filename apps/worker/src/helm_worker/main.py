import time

from helm_observability.logging import get_logger, setup_logging
from helm_storage.db import SessionLocal
from helm_storage.repositories.agent_runs import AgentRunCreate, SQLAlchemyAgentRunRepository

from helm_worker.config import settings
from helm_worker.jobs.registry import JOBS

tracking_logger = get_logger("helm_worker.agent_runs")


def _create_run(job_name: str) -> int | None:
    try:
        with SessionLocal() as session:
            repo = SQLAlchemyAgentRunRepository(session)
            run = repo.create(
                AgentRunCreate(agent_name=f"{job_name}_workflow", source_type="worker", source_id=job_name)
            )
            return run.id
    except Exception as exc:  # noqa: BLE001
        tracking_logger.warning(
            "agent_run_create_failed",
            job=job_name,
            error_type=type(exc).__name__,
        )
        return None


def _mark_success(run_id: int | None) -> None:
    if run_id is None:
        return
    try:
        with SessionLocal() as session:
            repo = SQLAlchemyAgentRunRepository(session)
            repo.mark_succeeded(run_id)
    except Exception as exc:  # noqa: BLE001
        tracking_logger.warning(
            "agent_run_mark_success_failed",
            run_id=run_id,
            error_type=type(exc).__name__,
        )
        return


def _mark_failed(run_id: int | None, error_message: str) -> None:
    if run_id is None:
        return
    try:
        with SessionLocal() as session:
            repo = SQLAlchemyAgentRunRepository(session)
            repo.mark_failed(run_id, error_message=error_message[:512])
    except Exception as exc:  # noqa: BLE001
        tracking_logger.warning(
            "agent_run_mark_failed_failed",
            run_id=run_id,
            error_type=type(exc).__name__,
        )
        return


def run() -> None:
    setup_logging()
    logger = get_logger("helm_worker")

    logger.info("worker_started", poll_seconds=settings.worker_poll_seconds, jobs=list(JOBS))
    while True:
        for name, job in JOBS.items():
            run_id = _create_run(name)
            try:
                job()
                _mark_success(run_id)
            except Exception as exc:  # noqa: BLE001
                _mark_failed(run_id, error_message=f"{type(exc).__name__}: {str(exc)}")
                logger.error("worker_job_failed", job=name, run_id=run_id, error_type=type(exc).__name__)
        time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    run()
