from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import DraftReasoningArtifactORM
from helm_storage.repositories.contracts import NewDraftReasoningArtifact


class SQLAlchemyDraftReasoningArtifactRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, item: NewDraftReasoningArtifact) -> DraftReasoningArtifactORM:
        record = DraftReasoningArtifactORM(
            email_draft_id=item.email_draft_id,
            email_thread_id=item.email_thread_id,
            action_proposal_id=item.action_proposal_id,
            schema_version=item.schema_version,
            prompt_context=item.prompt_context,
            model_metadata=item.model_metadata,
            reasoning_payload=item.reasoning_payload,
            refinement_metadata=item.refinement_metadata or {},
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def list_for_draft(self, *, email_draft_id: int) -> list[DraftReasoningArtifactORM]:
        stmt = (
            select(DraftReasoningArtifactORM)
            .where(DraftReasoningArtifactORM.email_draft_id == email_draft_id)
            .order_by(DraftReasoningArtifactORM.id.desc())
        )
        return list(self._session.execute(stmt).scalars().all())
