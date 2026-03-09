from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import JobControlORM


class SQLAlchemyJobControlRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[JobControlORM]:
        statement = select(JobControlORM).order_by(JobControlORM.job_name.asc())
        return list(self._session.execute(statement).scalars().all())

    def get_by_job_name(self, job_name: str) -> JobControlORM | None:
        statement = select(JobControlORM).where(JobControlORM.job_name == job_name)
        return self._session.execute(statement).scalar_one_or_none()

    def is_paused(self, job_name: str) -> bool:
        record = self.get_by_job_name(job_name)
        return bool(record.paused) if record is not None else False

    def set_paused(self, *, job_name: str, paused: bool) -> JobControlORM:
        record = self.get_by_job_name(job_name)
        if record is None:
            record = JobControlORM(job_name=job_name, paused=paused)
            self._session.add(record)
        else:
            record.paused = paused
            self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record
