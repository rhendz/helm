from sqlalchemy import select
from sqlalchemy.orm import Session

from helm_storage.models import EmailAgentConfigORM
from helm_storage.repositories.contracts import EmailAgentConfigPatch


class SQLAlchemyEmailAgentConfigRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> EmailAgentConfigORM | None:
        stmt = select(EmailAgentConfigORM).order_by(EmailAgentConfigORM.id.asc())
        return self._session.execute(stmt).scalars().first()

    def get_or_create(self) -> EmailAgentConfigORM:
        existing = self.get()
        if existing is not None:
            return existing
        record = EmailAgentConfigORM()
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record

    def update(self, patch: EmailAgentConfigPatch) -> EmailAgentConfigORM:
        record = self.get_or_create()
        if patch.approval_required_before_send is not None:
            record.approval_required_before_send = patch.approval_required_before_send
        if patch.default_follow_up_business_days is not None:
            record.default_follow_up_business_days = patch.default_follow_up_business_days
        if patch.timezone_name is not None:
            record.timezone_name = patch.timezone_name
        if patch.last_history_cursor is not None:
            record.last_history_cursor = patch.last_history_cursor
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record
