from collections.abc import Callable

from helm_worker.jobs import (
    digest,
    email_deep_seed,
    email_followup_scan,
    email_send_recovery,
    email_triage,
    replay,
    scheduled_thread_tasks,
)

Job = Callable[[], None]

JOBS: dict[str, Job] = {
    "email_deep_seed": email_deep_seed.run,
    "email_followup_scan": email_followup_scan.run,
    "email_send_recovery": email_send_recovery.run,
    "email_triage": email_triage.run,
    "digest": digest.run,
    "replay": replay.run,
    "scheduled_thread_tasks": scheduled_thread_tasks.run,
}
