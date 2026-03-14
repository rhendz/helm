from email_agent.replay_queue import run_replay_queue
from helm_storage.db import SessionLocal
from helm_storage.repositories.job_controls import SQLAlchemyJobControlRepository
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


def _build_job_control(*, job_name: str, paused: bool) -> dict[str, object]:
    return {"job_name": job_name, "paused": paused}


def list_job_controls(*, paused: bool | None = None) -> list[dict[str, object]]:
    persisted: dict[str, bool] = {}
    try:
        with SessionLocal() as session:
            repository = SQLAlchemyJobControlRepository(session)
            persisted = {row.job_name: bool(row.paused) for row in repository.list_all()}
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


def run_replay_job(*, limit: int) -> dict[str, object]:
    replay_control = get_job_control(job_name="replay")
    if replay_control is not None and bool(replay_control["paused"]):
        return {
            "status": "rejected",
            "job_name": "replay",
            "limit": limit,
            "processed_count": 0,
            "reason": "job_paused",
        }

    processed_count = run_replay_queue(limit=limit)
    return {
        "status": "accepted",
        "job_name": "replay",
        "limit": limit,
        "processed_count": processed_count,
        "reason": None,
    }
