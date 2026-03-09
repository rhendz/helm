from __future__ import annotations

from dataclasses import dataclass

from helm_agents.study_agent import extract_study_artifacts
from helm_observability.logging import get_logger
from helm_storage.repositories.study_ingest import (
    KnowledgeGapCreate,
    LearningTaskCreate,
    SQLAlchemyStudyIngestRepository,
    StudyDigestCreate,
)
from sqlalchemy.orm import Session

logger = get_logger("helm_orchestration.study_flow")


@dataclass(slots=True, frozen=True)
class StudyIngestArtifacts:
    study_session_id: int
    summary: str
    learning_task_ids: list[int]
    knowledge_gap_ids: list[int]
    digest_item_id: int | None
    agent_run_id: int


def run_study_ingest_flow(*, source_type: str, raw_text: str, db: Session) -> StudyIngestArtifacts:
    extraction = extract_study_artifacts(raw_text)
    repo = SQLAlchemyStudyIngestRepository(db)
    try:
        session_record = repo.create_study_session(
            source_type=source_type,
            raw_text=raw_text,
            summary=extraction.summary,
        )
        agent_run = repo.create_agent_run(
            agent_name="study_ingest",
            source_type=source_type,
            source_id=str(session_record.id),
        )

        gap_ids_by_topic: dict[str, int] = {}
        knowledge_gap_ids: list[int] = []
        for gap in extraction.knowledge_gaps:
            gap_record = repo.create_knowledge_gap(
                session_id=session_record.id,
                payload=KnowledgeGapCreate(
                    topic=gap.topic,
                    description=gap.description,
                    severity=gap.severity,
                ),
            )
            knowledge_gap_ids.append(gap_record.id)
            gap_ids_by_topic[gap.topic.lower()] = gap_record.id

        learning_task_ids: list[int] = []
        for task in extraction.learning_tasks:
            related_gap_id = None
            if task.related_gap_topic:
                related_gap_id = gap_ids_by_topic.get(task.related_gap_topic.lower())
            task_record = repo.create_learning_task(
                session_id=session_record.id,
                payload=LearningTaskCreate(
                    title=task.title,
                    description=task.description,
                    priority=task.priority,
                    related_gap_id=related_gap_id,
                ),
            )
            learning_task_ids.append(task_record.id)

        digest_item_id = None
        if extraction.digest_candidate is not None:
            digest_record = repo.create_study_digest_item(
                StudyDigestCreate(
                    title=extraction.digest_candidate.title,
                    summary=extraction.digest_candidate.summary,
                    priority=extraction.digest_candidate.priority,
                )
            )
            digest_item_id = digest_record.id

        repo.complete_agent_run(agent_run)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("study_ingest_failed", source_type=source_type, error=str(exc))
        raise

    logger.info(
        "study_ingest_completed",
        session_id=session_record.id,
        gaps=len(knowledge_gap_ids),
        tasks=len(learning_task_ids),
        has_digest_item=digest_item_id is not None,
    )
    return StudyIngestArtifacts(
        study_session_id=session_record.id,
        summary=extraction.summary,
        learning_task_ids=learning_task_ids,
        knowledge_gap_ids=knowledge_gap_ids,
        digest_item_id=digest_item_id,
        agent_run_id=agent_run.id,
    )
