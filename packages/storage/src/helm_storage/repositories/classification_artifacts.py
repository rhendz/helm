from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import ClassificationArtifactORM
from helm_storage.repositories.contracts import NewClassificationArtifact


class SQLAlchemyClassificationArtifactRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, item: NewClassificationArtifact) -> ClassificationArtifactORM:
        record = ClassificationArtifactORM(
            email_thread_id=item.email_thread_id,
            email_message_id=item.email_message_id,
            classification=item.classification,
            priority_score=item.priority_score,
            business_state=item.business_state,
            visible_labels=list(item.visible_labels),
            action_reason=item.action_reason,
            resurfacing_source=item.resurfacing_source,
            confidence_band=item.confidence_band,
            decision_context=item.decision_context or {},
            model_name=item.model_name,
            prompt_version=item.prompt_version,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def list_for_thread(self, *, email_thread_id: int) -> list[ClassificationArtifactORM]:
        stmt = (
            select(ClassificationArtifactORM)
            .where(ClassificationArtifactORM.email_thread_id == email_thread_id)
            .order_by(ClassificationArtifactORM.id.desc())
        )
        return list(self._session.execute(stmt).scalars().all())

    def list_for_message(self, *, email_message_id: int) -> list[ClassificationArtifactORM]:
        stmt = (
            select(ClassificationArtifactORM)
            .where(ClassificationArtifactORM.email_message_id == email_message_id)
            .order_by(ClassificationArtifactORM.id.desc())
        )
        return list(self._session.execute(stmt).scalars().all())
