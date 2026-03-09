from helm_storage.db import Base
from helm_storage.models import KnowledgeGapORM, LearningTaskORM, StudySessionORM
from helm_storage.repositories.study_ingest import SQLAlchemyStudyIngestRepository
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


def test_create_session_with_artifacts_persists_linked_records() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with session_factory() as session:
        repository = SQLAlchemyStudyIngestRepository(session)
        study_session = repository.create_session_with_artifacts(
            source_type="manual",
            raw_text="Gap: weak in dijkstra\nTODO: practice dijkstra",
            summary="Practiced graph algorithms.",
            knowledge_gaps=[
                {"topic": "dijkstra", "description": "weak in dijkstra", "severity": "medium"}
            ],
            learning_tasks=[
                {
                    "title": "practice dijkstra",
                    "description": "solve 5 dijkstra problems",
                    "priority": 2,
                    "status": "open",
                    "related_gap_index": 0,
                }
            ],
        )

        persisted_session = session.execute(
            select(StudySessionORM).where(StudySessionORM.id == study_session.id)
        ).scalar_one()
        persisted_gap = session.execute(
            select(KnowledgeGapORM).where(KnowledgeGapORM.source_session_id == study_session.id)
        ).scalar_one()
        persisted_task = session.execute(select(LearningTaskORM)).scalar_one()

    assert persisted_session.summary == "Practiced graph algorithms."
    assert persisted_gap.topic == "dijkstra"
    assert persisted_task.related_gap_id == persisted_gap.id
