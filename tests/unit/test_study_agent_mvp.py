from __future__ import annotations

import importlib
import shutil
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

STUDY_AGENT_ROOT = Path(__file__).resolve().parents[2] / "apps" / "study-agent"
if str(STUDY_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDY_AGENT_ROOT))

artifact_writer = importlib.import_module("app.engine.artifact_writer")
write_session_artifact = artifact_writer.write_session_artifact
checkin_module = importlib.import_module("app.engine.checkin")
answer_checkin = checkin_module.answer_checkin
start_checkin = checkin_module.start_checkin
choose_recommendation = importlib.import_module("app.engine.prioritizer").choose_recommendation
reviewer_module = importlib.import_module("app.engine.reviewer")
apply_review_to_topic = reviewer_module.apply_review_to_topic
finalize_session_record = reviewer_module.finalize_session_record
next_review_date = importlib.import_module("app.engine.scheduler").next_review_date
llm_client_module = importlib.import_module("app.llm.client")
session_module = importlib.import_module("app.schemas.session")
ReviewResult = session_module.ReviewResult
SessionRecord = session_module.SessionRecord
storage_files = importlib.import_module("app.storage.files")


class StubLLMClient:
    def run_checkin_summary(self, payload: str) -> str:
        assert "Complaint" in payload
        return "Reduce scope on low-priority work and keep one hard focus."


def _copy_seed_data(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    shutil.copytree(STUDY_AGENT_ROOT / "data", data_dir)
    return data_dir


def test_recommendation_prefers_due_high_priority_course() -> None:
    courses = [
        storage_files.load_course_state("demo_user", "system-design"),
        storage_files.load_course_state("demo_user", "thai-intro"),
    ]

    recommendation = choose_recommendation(courses)

    assert recommendation.course_id == "system-design"
    assert recommendation.topic_id in {"caching-basics", "consistency-basics"}
    assert recommendation.mode == "lite"


def test_review_updates_topic_and_writes_session_artifact(tmp_path, monkeypatch) -> None:
    data_dir = _copy_seed_data(tmp_path)
    monkeypatch.setattr(storage_files, "USERS_DIR", data_dir / "users")

    course = storage_files.load_course_state("demo_user", "system-design")
    topic = next(item for item in course.topics if item.id == "caching-basics")
    record = SessionRecord(
        session_id="session-1",
        course_id=course.course_id,
        topic_id=topic.id,
        mode="full",
        status="in_progress",
        started_at="2026-03-10T10:00:00",
    )
    review = ReviewResult(
        score=0.82,
        what_was_right="You explained the role of caching and named a valid example.",
        what_was_missing="You skipped invalidation tradeoffs.",
        stronger_answer_guidance="State freshness tradeoffs and mention eviction or invalidation.",
        weak_signals=["cache invalidation"],
        next_step="Review invalidation patterns in two days.",
        mastery_delta=0.2,
        confidence="medium",
        corrected_notes="Caching reduces load and latency, but invalidation controls correctness.",
    )

    updated_topic = apply_review_to_topic(course, topic.id, review)
    finalized = finalize_session_record(record, review)
    storage_files.save_course_state("demo_user", course)
    storage_files.save_session_record("demo_user", finalized)
    artifact_path = write_session_artifact("demo_user", course, updated_topic, finalized, review)

    assert updated_topic.mastery > 0.42
    assert updated_topic.next_review is not None
    assert finalized.status == "completed"
    assert Path(artifact_path).exists()
    assert "What You Got Right" in Path(artifact_path).read_text(encoding="utf-8")


def test_scheduler_and_json_persistence_are_deterministic(tmp_path, monkeypatch) -> None:
    data_dir = _copy_seed_data(tmp_path)
    monkeypatch.setattr(storage_files, "USERS_DIR", data_dir / "users")

    course = storage_files.load_course_state("demo_user", "thai-intro")
    topic = next(item for item in course.topics if item.id == "pronouns")
    next_date = next_review_date(topic, 0.4)
    topic.next_review = next_date
    storage_files.save_course_state("demo_user", course)
    reloaded = storage_files.load_course_state("demo_user", "thai-intro")

    assert reloaded.topics[1].next_review == next_date
    assert next_date >= date.today().isoformat()


def test_review_normalization_handles_realistic_model_shape() -> None:
    result = llm_client_module._normalize_review_result(
        {
            "score": 5,
            "what_was_right": "Core idea is correct.",
            "what_was_missing": "Tradeoffs are missing.",
            "stronger_answer_guidance": "Add tradeoffs and one example.",
            "weak_signals": "depth, practical implications",
            "next_step": "Retry tomorrow.",
            "mastery_delta": 3,
            "confidence": 0.9,
            "corrected_notes": "Corrected notes.",
        }
    )

    assert result.score == 0.5
    assert result.mastery_delta == 0.3
    assert result.confidence == "high"
    assert result.weak_signals == ["depth", "practical implications"]


def test_review_answer_uses_structured_parse_and_normalizes(monkeypatch) -> None:
    class FakeResponses:
        def parse(self, **kwargs):
            assert kwargs["text_format"] is ReviewResult
            return SimpleNamespace(
                output_parsed=ReviewResult(
                    score=2.0,
                    what_was_right="You got the core idea.",
                    what_was_missing="You missed tradeoffs.",
                    stronger_answer_guidance="Add one concrete example.",
                    weak_signals=["precision"],
                    next_step="Retry tomorrow.",
                    mastery_delta=2.0,
                    confidence="high",
                    corrected_notes="Corrected notes.",
                )
            )

    def fake_openai(api_key):
        return SimpleNamespace(responses=FakeResponses())

    monkeypatch.setattr(llm_client_module, "OpenAI", fake_openai)
    settings = SimpleNamespace(openai_api_key="test-key", openai_model="gpt-5-mini")
    client = llm_client_module.LLMClient(settings)

    result = client.review_answer("payload")

    assert result.score == 0.2
    assert result.mastery_delta == 0.2
    assert result.confidence == "high"


def test_checkin_creates_weekly_artifact_and_clears_state(tmp_path, monkeypatch) -> None:
    data_dir = _copy_seed_data(tmp_path)
    monkeypatch.setattr(storage_files, "USERS_DIR", data_dir / "users")

    state = start_checkin("demo_user")
    assert state.questions[0]

    prompts = [
        "Thai feels fine. System design is the friction point.",
        "Prioritize system design more and Thai less next week.",
        "Caching basics is shakier than the JSON says.",
        "The current cadence is too much, reduce it a bit.",
    ]
    llm = StubLLMClient()
    completed = False
    message = ""
    for response in prompts:
        completed, message = answer_checkin("demo_user", response, llm)

    iso_year, iso_week, _ = date.today().isocalendar()
    artifact_path = (
        data_dir / "users" / "demo_user" / "weekly_reviews" / f"{iso_year}-W{iso_week:02d}.md"
    )

    assert completed is True
    assert "Weekly check-in saved." in message
    assert artifact_path.exists()
    assert storage_files.load_active_checkin("demo_user") is None
