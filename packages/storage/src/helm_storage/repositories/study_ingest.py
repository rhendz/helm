from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from helm_storage.models import (
    AgentRunORM,
    DigestItemORM,
    KnowledgeGapORM,
    LearningTaskORM,
    StudySessionORM,
)


@dataclass(slots=True)
class KnowledgeGapCreate:
    topic: str
    description: str
    severity: int = 3


@dataclass(slots=True)
class LearningTaskCreate:
    title: str
    description: str | None = None
    priority: int = 3
    status: str = "open"
    related_gap_id: int | None = None


@dataclass(slots=True)
class StudyDigestCreate:
    title: str
    summary: str
    priority: int = 3


class SQLAlchemyStudyIngestRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_study_session(
        self, *, source_type: str, raw_text: str, summary: str
    ) -> StudySessionORM:
        session_record = StudySessionORM(
            source_type=source_type,
            raw_text=raw_text,
            summary=summary,
        )
        self._session.add(session_record)
        self._session.flush()
        return session_record

    def create_knowledge_gap(
        self, *, session_id: int, payload: KnowledgeGapCreate
    ) -> KnowledgeGapORM:
        gap = KnowledgeGapORM(
            topic=payload.topic,
            description=payload.description,
            severity=payload.severity,
            source_session_id=session_id,
        )
        self._session.add(gap)
        self._session.flush()
        return gap

    def create_learning_task(
        self, *, session_id: int, payload: LearningTaskCreate
    ) -> LearningTaskORM:
        task = LearningTaskORM(
            title=payload.title,
            description=payload.description,
            priority=payload.priority,
            status=payload.status,
            related_gap_id=payload.related_gap_id,
            source_session_id=session_id,
        )
        self._session.add(task)
        self._session.flush()
        return task

    def create_study_digest_item(self, payload: StudyDigestCreate) -> DigestItemORM:
        digest_item = DigestItemORM(
            domain="study",
            title=payload.title,
            summary=payload.summary,
            priority=payload.priority,
        )
        self._session.add(digest_item)
        self._session.flush()
        return digest_item

    def create_agent_run(
        self, *, agent_name: str, source_type: str, source_id: str, status: str = "running"
    ) -> AgentRunORM:
        run = AgentRunORM(
            agent_name=agent_name,
            source_type=source_type,
            source_id=source_id,
            status=status,
        )
        self._session.add(run)
        self._session.flush()
        return run

    def complete_agent_run(
        self, run: AgentRunORM, *, status: str = "completed", error_message: str | None = None
    ) -> None:
        run.status = status
        run.error_message = error_message
        run.completed_at = datetime.now(UTC)
