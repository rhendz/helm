from helm_storage.db import SessionLocal
from helm_storage.repositories.job_controls import SQLAlchemyJobControlRepository
from sqlalchemy.exc import SQLAlchemyError


def list_job_controls() -> list[dict[str, object]]:
    try:
        with SessionLocal() as session:
            repository = SQLAlchemyJobControlRepository(session)
            return [
                {"job_name": row.job_name, "paused": bool(row.paused)}
                for row in repository.list_all()
            ]
    except SQLAlchemyError:
        return []


def set_job_pause(*, job_name: str, paused: bool) -> dict[str, object]:
    try:
        with SessionLocal() as session:
            repository = SQLAlchemyJobControlRepository(session)
            row = repository.set_paused(job_name=job_name, paused=paused)
            return {"job_name": row.job_name, "paused": bool(row.paused)}
    except SQLAlchemyError:
        return {"job_name": job_name, "paused": paused}
