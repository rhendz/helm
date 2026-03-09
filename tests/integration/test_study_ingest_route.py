from pathlib import Path

import helm_storage.models  # noqa: F401
from fastapi.testclient import TestClient
from helm_api.dependencies import get_db
from helm_api.main import app
from helm_storage.db import Base
from helm_storage.models import (
    AgentRunORM,
    DigestItemORM,
    KnowledgeGapORM,
    LearningTaskORM,
    StudySessionORM,
)
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def test_study_ingest_persists_artifacts() -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    fixture_path = Path("tests/fixtures/study/manual_ingest_note.txt")
    payload = {
        "source_type": "manual_note",
        "raw_text": fixture_path.read_text(encoding="utf-8"),
    }
    client = TestClient(app)
    response = client.post("/v1/study/ingest", json=payload)
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert len(body["knowledge_gap_ids"]) == 2
    assert len(body["learning_task_ids"]) == 2
    assert body["agent_run_id"] > 0

    with Session(engine) as session:
        assert session.get(StudySessionORM, body["study_session_id"]) is not None

        gap_count = session.scalar(select(func.count()).select_from(KnowledgeGapORM))
        task_count = session.scalar(select(func.count()).select_from(LearningTaskORM))
        run_count = session.scalar(select(func.count()).select_from(AgentRunORM))
        digest_count = session.scalar(select(func.count()).select_from(DigestItemORM))

        assert gap_count == 2
        assert task_count == 2
        assert run_count == 1
        assert digest_count == 1
