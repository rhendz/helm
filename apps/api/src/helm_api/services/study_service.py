from helm_orchestration.study_flow import run_study_ingest_flow
from sqlalchemy.orm import Session


def ingest_manual_study_note(source_type: str, raw_text: str, db: Session) -> dict:
    result = run_study_ingest_flow(source_type=source_type, raw_text=raw_text, db=db)
    return {
        "status": "accepted",
        "source_type": source_type,
        "study_session_id": result.study_session_id,
        "summary": result.summary,
        "learning_task_ids": result.learning_task_ids,
        "knowledge_gap_ids": result.knowledge_gap_ids,
        "digest_item_id": result.digest_item_id,
        "agent_run_id": result.agent_run_id,
    }
