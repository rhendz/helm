from collections.abc import Callable

from helm_worker.jobs import (
    digest,
    email_deep_seed,
    email_triage,
    replay,
    scheduled_thread_tasks,
    study,
)

Job = Callable[[], None]

JOBS: dict[str, Job] = {
    "email_deep_seed": email_deep_seed.run,
    "email_triage": email_triage.run,
    "digest": digest.run,
    "study": study.run,
    "replay": replay.run,
    "scheduled_thread_tasks": scheduled_thread_tasks.run,
}
