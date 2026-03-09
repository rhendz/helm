from pathlib import Path

from helm_agents.study_agent import extract_study_artifacts


def test_extract_study_artifacts_parses_summary_tasks_gaps() -> None:
    fixture_path = Path("tests/fixtures/study/manual_ingest_note.txt")
    raw_text = fixture_path.read_text(encoding="utf-8")

    extraction = extract_study_artifacts(raw_text)

    assert "Practiced binary search and heap questions" in extraction.summary
    assert len(extraction.knowledge_gaps) == 2
    assert len(extraction.learning_tasks) == 2
    assert extraction.digest_candidate is not None
    assert extraction.digest_candidate.title.startswith("Study gap:")
