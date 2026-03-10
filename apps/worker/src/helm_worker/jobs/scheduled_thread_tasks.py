from helm_observability.logging import get_logger
from helm_orchestration.scheduled_tasks import run_due_scheduled_thread_tasks

logger = get_logger("helm_worker.jobs.scheduled_thread_tasks")


def run() -> None:
    result = run_due_scheduled_thread_tasks()
    logger.info(
        "scheduled_thread_tasks_job_tick",
        processed_count=result.processed_count,
        skipped_count=result.skipped_count,
    )
