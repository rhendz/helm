from email_agent.adapters import build_helm_runtime
from email_agent.scheduling import run_due_scheduled_thread_tasks
from helm_observability.logging import get_logger

logger = get_logger("helm_worker.jobs.scheduled_thread_tasks")


def run() -> None:
    result = run_due_scheduled_thread_tasks(runtime=build_helm_runtime())
    logger.info(
        "scheduled_thread_tasks_job_tick",
        processed_count=result.processed_count,
        skipped_count=result.skipped_count,
    )
