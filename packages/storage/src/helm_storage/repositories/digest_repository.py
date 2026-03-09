from dataclasses import dataclass
from datetime import datetime

from helm_observability.logging import get_logger
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from helm_storage.models import ActionItemORM

logger = get_logger("helm_storage.repositories.digest")


@dataclass(frozen=True)
class ActionDigestRecord:
    id: int
    title: str
    description: str | None
    priority: int
    created_at: datetime | None


@dataclass(frozen=True)
class DigestItemRecord:
    id: int
    domain: str
    title: str
    summary: str | None
    priority: int
    created_at: datetime | None


@dataclass(frozen=True)
class DraftDigestRecord:
    id: int
    channel_type: str
    status: str
    preview: str
    created_at: datetime | None


@dataclass(frozen=True)
class StudyPriorityRecord:
    id: int
    title: str
    priority: int
    created_at: datetime | None


class DigestInputRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_open_action_items(self, limit: int = 20) -> list[ActionDigestRecord]:
        try:
            stmt = (
                select(
                    ActionItemORM.id,
                    ActionItemORM.title,
                    ActionItemORM.description,
                    ActionItemORM.priority,
                    ActionItemORM.created_at,
                )
                .where(ActionItemORM.status == "open")
                .order_by(ActionItemORM.priority.asc(), ActionItemORM.created_at.desc())
                .limit(limit)
            )
            rows = self._session.execute(stmt).all()
            return [
                ActionDigestRecord(
                    id=row.id,
                    title=row.title,
                    description=row.description,
                    priority=row.priority,
                    created_at=row.created_at,
                )
                for row in rows
            ]
        except SQLAlchemyError as exc:
            logger.warning("digest_open_actions_query_failed", error=str(exc))
            return []

    def list_high_priority_digest_items(self, limit: int = 20) -> list[DigestItemRecord]:
        if not self._table_exists("digest_items"):
            return []
        try:
            rows = self._session.execute(
                text(
                    """
                    SELECT id, domain, title, summary, priority, created_at
                    FROM digest_items
                    ORDER BY priority ASC, created_at DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            ).mappings()
            return [
                DigestItemRecord(
                    id=row["id"],
                    domain=row["domain"],
                    title=row["title"],
                    summary=row["summary"],
                    priority=row["priority"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]
        except SQLAlchemyError as exc:
            logger.warning("digest_items_query_failed", error=str(exc))
            return []

    def list_pending_drafts(self, limit: int = 20) -> list[DraftDigestRecord]:
        if not self._table_exists("draft_replies"):
            return []
        try:
            rows = self._session.execute(
                text(
                    """
                    SELECT id, channel_type, status, draft_text, created_at
                    FROM draft_replies
                    WHERE status IN ('pending', 'pending_approval', 'needs_review')
                    ORDER BY created_at ASC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            ).mappings()
            return [
                DraftDigestRecord(
                    id=row["id"],
                    channel_type=row["channel_type"],
                    status=row["status"],
                    preview=(row["draft_text"] or "")[:120],
                    created_at=row["created_at"],
                )
                for row in rows
            ]
        except SQLAlchemyError as exc:
            logger.warning("digest_pending_drafts_query_failed", error=str(exc))
            return []

    def list_study_priorities(self, limit: int = 20) -> list[StudyPriorityRecord]:
        if not self._table_exists("learning_tasks"):
            return []
        try:
            rows = self._session.execute(
                text(
                    """
                    SELECT id, title, priority, created_at
                    FROM learning_tasks
                    WHERE status IN ('open', 'in_progress')
                    ORDER BY priority ASC, created_at DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            ).mappings()
            return [
                StudyPriorityRecord(
                    id=row["id"],
                    title=row["title"],
                    priority=row["priority"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]
        except SQLAlchemyError as exc:
            logger.warning("digest_study_priorities_query_failed", error=str(exc))
            return []

    def _table_exists(self, table_name: str) -> bool:
        bind = self._session.get_bind()
        if bind is None:
            return False
        try:
            return inspect(bind).has_table(table_name)
        except SQLAlchemyError as exc:
            logger.warning("digest_table_inspection_failed", table=table_name, error=str(exc))
            return False
