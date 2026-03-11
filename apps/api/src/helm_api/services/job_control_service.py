from helm_storage.db import SessionLocal
from helm_storage.repositories.job_controls import SQLAlchemyJobControlRepository
from sqlalchemy.exc import SQLAlchemyError


def list_job_controls(*, paused: bool | None = None) -> list[dict[str, object]]:
    try:
        with SessionLocal() as session:
            repository = SQLAlchemyJobControlRepository(session)
            items = [
                {"job_name": row.job_name, "paused": bool(row.paused)}
                for row in repository.list_all()
            ]
            if paused is None:
                return items
            return [item for item in items if bool(item["paused"]) is paused]
    except SQLAlchemyError:
        return []


def get_job_control(*, job_name: str) -> dict[str, object] | None:
    try:
        with SessionLocal() as session:
            repository = SQLAlchemyJobControlRepository(session)
            row = repository.get_by_job_name(job_name)
            if row is None:
                return None
            return {"job_name": row.job_name, "paused": bool(row.paused)}
    except SQLAlchemyError:
        return None


def set_job_pause(*, job_name: str, paused: bool) -> dict[str, object]:
    try:
        with SessionLocal() as session:
            repository = SQLAlchemyJobControlRepository(session)
            row = repository.set_paused(job_name=job_name, paused=paused)
            return {"job_name": row.job_name, "paused": bool(row.paused)}
    except SQLAlchemyError:
        return {"job_name": job_name, "paused": paused}
