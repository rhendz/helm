from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import DraftReplyORM, LinkedInMessageORM, OpportunityORM


class SQLAlchemyLinkedInTriageRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_recent_messages(self, *, limit: int) -> list[LinkedInMessageORM]:
        statement = select(LinkedInMessageORM).order_by(LinkedInMessageORM.id.desc()).limit(limit)
        return list(self._session.execute(statement).scalars().all())

    def get_opportunity_by_source(self, *, source_id: str) -> OpportunityORM | None:
        statement = select(OpportunityORM).where(
            OpportunityORM.channel_source == "linkedin",
            OpportunityORM.notes == source_id,
        )
        return self._session.execute(statement).scalar_one_or_none()

    def create_opportunity(
        self, *, source_id: str, company: str, role_title: str
    ) -> OpportunityORM:
        opportunity = OpportunityORM(
            company=company,
            role_title=role_title,
            channel_source="linkedin",
            notes=source_id,
            priority_score=60,
            status="open",
        )
        self._session.add(opportunity)
        self._session.flush()
        return opportunity

    def get_latest_linkedin_draft_for_thread(self, *, thread_id: str) -> DraftReplyORM | None:
        statement = (
            select(DraftReplyORM)
            .where(
                DraftReplyORM.channel_type == "linkedin",
                DraftReplyORM.thread_id == thread_id,
            )
            .order_by(DraftReplyORM.id.desc())
        )
        return self._session.execute(statement).scalar_one_or_none()

    def create_linkedin_draft(self, *, thread_id: str, text: str) -> DraftReplyORM:
        draft = DraftReplyORM(
            channel_type="linkedin",
            thread_id=thread_id,
            draft_text=text,
            status="pending",
        )
        self._session.add(draft)
        self._session.flush()
        return draft

    def commit(self) -> None:
        self._session.commit()
