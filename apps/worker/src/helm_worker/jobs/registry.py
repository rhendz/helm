from collections.abc import Callable

from helm_worker.jobs import digest, email_triage, replay, scheduled_thread_tasks, study, workflow_runs

Job = Callable[[], None]

JOBS: dict[str, Job] = {
    "email_triage": email_triage.run,
    "digest": digest.run,
    "study": study.run,
    "replay": replay.run,
    "scheduled_thread_tasks": scheduled_thread_tasks.run,
    "workflow_runs": workflow_runs.run,
}
