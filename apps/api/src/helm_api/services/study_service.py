def ingest_manual_study_note(source_type: str, raw_text: str) -> dict:
    from helm_agents.study_agent import extract_study_artifacts
    from helm_storage.db import SessionLocal
    from helm_storage.repositories.study_ingest import SQLAlchemyStudyIngestRepository
    from sqlalchemy.exc import SQLAlchemyError

    artifacts = extract_study_artifacts(raw_text=raw_text)
    session_id: int | None = None
    persisted = False

    try:
        with SessionLocal() as session:
            repository = SQLAlchemyStudyIngestRepository(session)
            study_session = repository.create_session_with_artifacts(
                source_type=source_type,
                raw_text=raw_text,
                summary=artifacts["summary"],
                knowledge_gaps=artifacts["knowledge_gaps"],
                learning_tasks=artifacts["learning_tasks"],
            )
            session_id = study_session.id
            persisted = True
    except SQLAlchemyError:
        persisted = False

    return {
        "status": "accepted",
        "source_type": source_type,
        "chars": len(raw_text),
        "summary": artifacts["summary"],
        "task_count": len(artifacts["learning_tasks"]),
        "gap_count": len(artifacts["knowledge_gaps"]),
        "session_id": session_id,
        "persisted": persisted,
    }
