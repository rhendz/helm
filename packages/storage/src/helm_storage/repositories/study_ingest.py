from datetime import datetime

from sqlalchemy.orm import Session

from helm_storage.models import KnowledgeGapORM, LearningTaskORM, StudySessionORM


class SQLAlchemyStudyIngestRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_session_with_artifacts(
        self,
        source_type: str,
        raw_text: str,
        summary: str,
        knowledge_gaps: list[dict],
        learning_tasks: list[dict],
    ) -> StudySessionORM:
        study_session = StudySessionORM(source_type=source_type, raw_text=raw_text, summary=summary)
        self._session.add(study_session)
        self._session.flush()

        gap_ids_by_index: dict[int, int] = {}
        for gap_index, gap_payload in enumerate(knowledge_gaps):
            gap = KnowledgeGapORM(
                topic=gap_payload["topic"],
                description=gap_payload.get("description") or gap_payload["topic"],
                severity=_to_severity_int(gap_payload.get("severity", 2)),
                source_session_id=study_session.id,
            )
            self._session.add(gap)
            self._session.flush()
            gap_ids_by_index[gap_index] = gap.id

        for task_payload in learning_tasks:
            due_at = task_payload.get("due_at")
            if isinstance(due_at, str):
                due_at = datetime.fromisoformat(due_at)
            related_gap_index = task_payload.get("related_gap_index")
            related_gap_id = (
                gap_ids_by_index.get(related_gap_index) if related_gap_index is not None else None
            )

            task = LearningTaskORM(
                title=task_payload["title"],
                description=task_payload.get("description"),
                priority=task_payload.get("priority", 3),
                status=task_payload.get("status", "open"),
                due_at=due_at,
                related_gap_id=related_gap_id,
            )
            self._session.add(task)

        self._session.commit()
        self._session.refresh(study_session)
        return study_session


def _to_severity_int(value: int | str) -> int:
    if isinstance(value, int):
        return value
    lowered = str(value).strip().lower()
    mapping = {"high": 1, "medium": 2, "low": 3}
    return mapping.get(lowered, 2)
