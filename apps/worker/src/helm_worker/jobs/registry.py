from collections.abc import Callable

from helm_worker.jobs import digest, email_triage, study

Job = Callable[[], None]

JOBS: dict[str, Job] = {
    "email_triage": email_triage.run,
    "digest": digest.run,
    "study": study.run,
}
