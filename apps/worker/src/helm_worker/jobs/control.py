from helm_observability.logging import get_logger
from helm_storage.db import SessionLocal
from helm_storage.repositories.job_controls import SQLAlchemyJobControlRepository
from sqlalchemy.exc import SQLAlchemyError

logger = get_logger("helm_worker.jobs.control")


def is_job_paused(job_name: str) -> bool:
    try:
        with SessionLocal() as session:
            repository = SQLAlchemyJobControlRepository(session)
            return repository.is_paused(job_name)
    except SQLAlchemyError:
        logger.warning("job_control_query_failed", job_name=job_name)
        return False
