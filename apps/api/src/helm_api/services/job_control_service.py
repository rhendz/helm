from helm_storage.db import SessionLocal
from helm_storage.repositories.job_controls import SQLAlchemyJobControlRepository
from helm_worker.jobs import replay as replay_job
from helm_worker.jobs.control import is_job_paused
from helm_worker.jobs.registry import JOBS
from sqlalchemy.exc import SQLAlchemyError

KNOWN_JOB_NAMES = (
    "digest",
    "email_deep_seed",
    "email_followup_scan",
    "email_reconciliation_sweep",
    "email_send_recovery",
    "email_triage",
    "replay",
    "scheduled_thread_tasks",
)
MANUALLY_RUNNABLE_JOB_NAMES = frozenset(job_name for job_name in JOBS if job_name != "replay")


def _build_job_control(*, job_name: str, paused: bool) -> dict[str, object]:
    return {"job_name": job_name, "paused": paused}


def list_job_controls(*, paused: bool | None = None) -> list[dict[str, object]]:
    persisted: dict[str, bool] = {}
    try:
        with SessionLocal() as session:
            repository = SQLAlchemyJobControlRepository(session)
            persisted = {
                row.job_name: bool(row.paused) for row in repository.list_all()
            }
    except SQLAlchemyError:
        persisted = {}

    items = [
        _build_job_control(job_name=job_name, paused=persisted.get(job_name, False))
        for job_name in KNOWN_JOB_NAMES
    ]
    if paused is None:
        return items
    return [item for item in items if bool(item["paused"]) is paused]


def get_job_control(*, job_name: str) -> dict[str, object] | None:
    if job_name not in KNOWN_JOB_NAMES:
        return None
    try:
        with SessionLocal() as session:
            repository = SQLAlchemyJobControlRepository(session)
            row = repository.get_by_job_name(job_name)
            if row is None:
                return _build_job_control(job_name=job_name, paused=False)
            return _build_job_control(job_name=row.job_name, paused=bool(row.paused))
    except SQLAlchemyError:
        return _build_job_control(job_name=job_name, paused=False)


def set_job_pause(*, job_name: str, paused: bool) -> dict[str, object]:
    try:
        with SessionLocal() as session:
            repository = SQLAlchemyJobControlRepository(session)
            row = repository.set_paused(job_name=job_name, paused=paused)
            return {"job_name": row.job_name, "paused": bool(row.paused)}
    except SQLAlchemyError:
        return {"job_name": job_name, "paused": paused}


def run_job(*, job_name: str) -> dict[str, object]:
    if job_name == "replay":
        return {
            "status": "rejected",
            "job_name": job_name,
            "reason": "use_replay_run_endpoint",
        }

    job = JOBS.get(job_name)
    if job is None:
        return {
            "status": "rejected",
            "job_name": job_name,
            "reason": "unknown_job",
        }
    if job_name not in MANUALLY_RUNNABLE_JOB_NAMES:
        return {
            "status": "rejected",
            "job_name": job_name,
            "reason": "manual_run_unsupported",
        }
    if is_job_paused(job_name):
        return {
            "status": "rejected",
            "job_name": job_name,
            "reason": "job_paused",
        }

    job()
    return {
        "status": "accepted",
        "job_name": job_name,
        "reason": None,
    }


def run_replay_job(*, limit: int) -> dict[str, object]:
    if is_job_paused("replay"):
        return {
            "status": "rejected",
            "job_name": "replay",
            "limit": limit,
            "processed_count": 0,
            "reason": "job_paused",
        }

    processed_count = replay_job.run(limit=limit)
    return {
        "status": "accepted",
        "job_name": "replay",
        "limit": limit,
        "processed_count": processed_count,
        "reason": None,
    }
