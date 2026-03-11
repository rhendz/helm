from email_agent.scheduling import run_due_scheduled_thread_tasks
from helm_observability.logging import get_logger
from helm_runtime.email_agent import build_email_agent_runtime

logger = get_logger("helm_worker.jobs.scheduled_thread_tasks")


def run() -> None:
    result = run_due_scheduled_thread_tasks(runtime=build_email_agent_runtime())
    logger.info(
        "scheduled_thread_tasks_job_tick",
        processed_count=result.processed_count,
        skipped_count=result.skipped_count,
        failed_count=result.failed_count,
    )
