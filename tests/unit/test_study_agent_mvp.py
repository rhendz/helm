from __future__ import annotations

import importlib
import shutil
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

STUDY_AGENT_ROOT = Path(__file__).resolve().parents[2] / "apps" / "study-agent"
if str(STUDY_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDY_AGENT_ROOT))

llm_client_module = importlib.import_module("app.llm.client")
onboarding = importlib.import_module("app.onboarding")
prioritizer = importlib.import_module("app.engine.prioritizer")
rules = importlib.import_module("app.engine.rules")
session_runner = importlib.import_module("app.engine.session_runner")
storage_files = importlib.import_module("app.storage.files")
course_module = importlib.import_module("app.schemas.course")
session_module = importlib.import_module("app.schemas.session")
ReviewResult = session_module.ReviewResult
CourseState = course_module.CourseState
TopicState = course_module.TopicState
TopicPerformance = course_module.TopicPerformance
AdherenceState = course_module.AdherenceState


def _copy_seed_data(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    shutil.copytree(STUDY_AGENT_ROOT / "data", data_dir)
    return data_dir


def _make_course(
    *,
    course_id: str = "test-course",
    title: str = "Test Course",
    priority: int = 3,
    topics: list[TopicState],
    sessions_per_week: int = 3,
) -> CourseState:
    return CourseState(
        course_id=course_id,
        title=title,
        goal="Test goal",
        status="active",
        priority=priority,
        cadence={"sessions_per_week": sessions_per_week, "target_minutes": 25, "deadline": None},
        adherence=AdherenceState(),
        topics=topics,
        last_session_date=None,
        weekly_checkin_needed=True,
    )


def test_seeded_recommendation_uses_recovery_stage_and_hydrated_metadata() -> None:
    courses = [
        storage_files.load_course_state("demo_user", "system-design"),
        storage_files.load_course_state("demo_user", "thai-intro"),
    ]

    recommendation = prioritizer.choose_recommendation(courses)
    chosen_topic = next(
        topic
        for course in courses
        if course.course_id == recommendation.course_id
        for topic in course.topics
        if topic.id == recommendation.topic_id
    )

    assert recommendation.policy_stage == "recovery"
    assert recommendation.topic_id == "caching-basics"
    assert recommendation.breakdown.recovery_pressure > 0
    assert recommendation.audit is not None
    assert recommendation.audit.winning_factors
    assert chosen_topic.starter is True
    assert chosen_topic.review_weight > 1.0
    assert "recovery" in recommendation.reason


def test_advancement_prefers_starter_then_respects_next_topic_progression() -> None:
    starter = TopicState(
        id="starter",
        name="Starter",
        state="unseen",
        mastery=0.05,
        confidence="low",
        starter=True,
        priority_within_course=5,
        next_topics=["follow-up"],
    )
    follow_up = TopicState(
        id="follow-up",
        name="Follow Up",
        state="unseen",
        mastery=0.05,
        confidence="low",
        prerequisites=["starter"],
        priority_within_course=4,
    )
    course = _make_course(topics=[starter, follow_up])

    first = prioritizer.choose_recommendation([course])
    assert first.policy_stage == "advancement"
    assert first.topic_id == "starter"

    starter.state = "solid"
    starter.mastery = 0.82
    starter.last_seen = date.today().isoformat()
    starter.next_review = (date.today() + timedelta(days=7)).isoformat()
    starter.cooldown_until = (date.today() + timedelta(days=2)).isoformat()

    second = prioritizer.choose_recommendation([course])
    assert second.policy_stage == "advancement"
    assert second.topic_id == "follow-up"
    assert second.breakdown.progression_bonus > 0


def test_prerequisites_block_advancement_for_unseen_topic() -> None:
    foundation = TopicState(
        id="foundation",
        name="Foundation",
        state="learning",
        mastery=0.4,
        confidence="low",
        priority_within_course=5,
        starter=True,
    )
    blocked = TopicState(
        id="blocked",
        name="Blocked Topic",
        state="unseen",
        mastery=0.05,
        confidence="low",
        prerequisites=["foundation"],
        priority_within_course=5,
    )
    course = _make_course(topics=[foundation, blocked])

    recommendation = prioritizer.choose_recommendation([course])

    assert recommendation.topic_id == "foundation"
    assert recommendation.audit is not None
    assert recommendation.audit.alternatives
    assert "Blocked from beating" in recommendation.audit.alternatives[0].why_not


def test_seen_learning_topic_is_not_mislabeled_as_advancement() -> None:
    starter = TopicState(
        id="starter",
        name="Starter",
        state="learning",
        mastery=0.55,
        confidence="medium",
        starter=True,
        priority_within_course=5,
        next_topics=["next"],
        last_seen="2026-03-09",
        next_review="2026-03-12",
    )
    next_topic = TopicState(
        id="next",
        name="Next",
        state="unseen",
        mastery=0.05,
        confidence="low",
        prerequisites=["starter"],
        priority_within_course=4,
    )
    course = _make_course(topics=[starter, next_topic])

    recommendation = prioritizer.choose_recommendation([course])

    assert recommendation.topic_id == "starter"
    assert recommendation.policy_stage == "consolidation"
    assert "advancement" not in recommendation.reason.split("because of", 1)[0].lower()
    assert "consolidation pressure" in recommendation.reason


def test_shallow_success_does_not_unlock_prerequisite_progression() -> None:
    starter = TopicState(
        id="starter",
        name="Starter",
        state="learning",
        mastery=0.55,
        confidence="medium",
        starter=True,
        priority_within_course=5,
        next_topics=["next"],
        last_seen="2026-03-09",
        next_review="2026-03-10",
    )
    next_topic = TopicState(
        id="next",
        name="Next",
        state="unseen",
        mastery=0.05,
        confidence="low",
        prerequisites=["starter"],
        priority_within_course=4,
    )
    course = _make_course(topics=[starter, next_topic])
    session = session_module.SessionRecord(
        session_id="s",
        user_id="u",
        course_id=course.course_id,
        topic_id="starter",
        mode="full",
        policy_stage="consolidation",
        recommendation_reason="test",
        recommendation_breakdown=session_module.RecommendationBreakdown(),
        status="awaiting_answer",
        started_at="2026-03-10T00:00:00+00:00",
    )
    review = ReviewResult(
        score=0.62,
        what_was_right="Okay",
        what_was_missing="Still weak",
        stronger_answer_guidance="Repeat it",
        weak_signals=["detail"],
        next_step="Do it again",
        corrected_notes="notes",
    )

    course, _ = rules.apply_session_completion(
        course,
        "starter",
        session,
        review,
        now=datetime(2026, 3, 10, tzinfo=UTC),
    )
    recommendation = prioritizer.choose_recommendation([course])

    assert recommendation.topic_id == "starter"
    assert recommendation.policy_stage == "consolidation"
    assert recommendation.audit is not None
    assert any("prerequisite" in alt.why_not.lower() for alt in recommendation.audit.alternatives)


def test_cooldown_reduces_overfocus_after_recent_success() -> None:
    strong_recent = [
        TopicPerformance(
            date=(date.today() - timedelta(days=1)).isoformat(),
            mode="full",
            score=0.8,
            weak_signals=[],
            outcome="completed_full",
        ),
        TopicPerformance(
            date=(date.today() - timedelta(days=2)).isoformat(),
            mode="full",
            score=0.78,
            weak_signals=[],
            outcome="completed_full",
        ),
    ]
    cooled_topic = TopicState(
        id="cooled",
        name="Cooled Topic",
        state="learning",
        mastery=0.7,
        confidence="medium",
        last_seen=(date.today() - timedelta(days=1)).isoformat(),
        next_review=date.today().isoformat(),
        cooldown_until=(date.today() + timedelta(days=2)).isoformat(),
        recent_history=strong_recent,
        priority_within_course=5,
    )
    other_due = TopicState(
        id="other",
        name="Other Topic",
        state="learning",
        mastery=0.55,
        confidence="medium",
        last_seen=(date.today() - timedelta(days=4)).isoformat(),
        next_review=date.today().isoformat(),
        priority_within_course=4,
    )
    course = _make_course(topics=[cooled_topic, other_due], priority=4)

    recommendation = prioritizer.choose_recommendation([course])

    assert recommendation.topic_id == "other"
    assert recommendation.breakdown.cooldown_penalty == 0


def test_rules_apply_full_and_lite_differently_and_keep_compact_history(
    tmp_path,
    monkeypatch,
) -> None:
    data_dir = _copy_seed_data(tmp_path)
    monkeypatch.setattr(storage_files, "USERS_DIR", data_dir / "users")

    course_full = storage_files.load_course_state("demo_user", "system-design")
    course_lite = storage_files.load_course_state("demo_user", "system-design")
    topic_full = next(topic for topic in course_full.topics if topic.id == "caching-basics")
    topic_lite = next(topic for topic in course_lite.topics if topic.id == "caching-basics")
    strong_recent = [
        TopicPerformance(
            date=(date.today() - timedelta(days=1)).isoformat(),
            mode="full",
            score=0.8,
            weak_signals=[],
            outcome="completed_full",
        ),
        TopicPerformance(
            date=(date.today() - timedelta(days=2)).isoformat(),
            mode="full",
            score=0.82,
            weak_signals=[],
            outcome="completed_full",
        ),
    ]
    topic_full.recent_history = list(strong_recent)
    topic_lite.recent_history = list(strong_recent)
    now = rules.now_utc()
    review = ReviewResult(
        score=0.82,
        what_was_right="Good",
        what_was_missing="Minor gap",
        stronger_answer_guidance="Add one tradeoff.",
        weak_signals=["tradeoffs"],
        next_step="Review later.",
        corrected_notes="Corrected notes.",
    )
    session_full = session_module.SessionRecord(
        session_id="full-1",
        user_id="demo_user",
        course_id=course_full.course_id,
        topic_id=topic_full.id,
        mode="full",
        policy_stage="consolidation",
        recommendation_reason="test",
        recommendation_breakdown=session_module.RecommendationBreakdown(),
        status="awaiting_answer",
        started_at=now.isoformat(),
    )
    session_lite = session_module.SessionRecord(
        session_id="lite-1",
        user_id="demo_user",
        course_id=course_lite.course_id,
        topic_id=topic_lite.id,
        mode="lite",
        policy_stage="recovery",
        recommendation_reason="test",
        recommendation_breakdown=session_module.RecommendationBreakdown(),
        status="awaiting_answer",
        started_at=now.isoformat(),
    )

    course_full, session_full = rules.apply_session_completion(
        course_full,
        topic_full.id,
        session_full,
        review,
        now=now,
    )
    course_lite, session_lite = rules.apply_session_completion(
        course_lite,
        topic_lite.id,
        session_lite,
        review,
        now=now,
    )

    assert topic_full.mastery > topic_lite.mastery
    assert course_full.adherence.completed_full == 4
    assert course_lite.adherence.completed_lite == 2
    assert len(topic_full.recent_history) <= rules.RECENT_HISTORY_LIMIT
    assert topic_full.cooldown_until is not None
    assert session_full.status == "completed"
    assert session_lite.status == "completed"


def test_repeated_failures_force_next_day_review_and_clear_cooldown() -> None:
    topic = TopicState(
        id="fragile",
        name="Fragile Topic",
        state="learning",
        mastery=0.52,
        confidence="medium",
        cooldown_until=(date.today() + timedelta(days=3)).isoformat(),
        recent_history=[
            TopicPerformance(
                date=(date.today() - timedelta(days=1)).isoformat(),
                mode="lite",
                score=0.3,
                weak_signals=["recall"],
                outcome="completed_lite",
            ),
            TopicPerformance(
                date=(date.today() - timedelta(days=2)).isoformat(),
                mode="lite",
                score=0.2,
                weak_signals=["recall"],
                outcome="missed",
            ),
        ],
    )
    course = _make_course(topics=[topic])

    updated = rules.apply_miss(course, "fragile", "bad day", now=rules.now_utc())
    fragile = next(item for item in updated.topics if item.id == "fragile")

    assert fragile.next_review == (date.today() + timedelta(days=1)).isoformat()
    assert fragile.cooldown_until is None
    assert updated.adherence.miss_streak == 1


def test_recommendation_audit_is_persisted(tmp_path, monkeypatch) -> None:
    data_dir = _copy_seed_data(tmp_path)
    monkeypatch.setattr(storage_files, "USERS_DIR", data_dir / "users")

    recommendation = session_runner.recommend_for_today("demo_user", persist_audit=True)
    audit_dir = data_dir / "users" / "demo_user" / "recommendations"
    audit_files = sorted(audit_dir.glob("*.json"))

    assert recommendation.audit is not None
    assert audit_files
    payload = storage_files.read_json(audit_files[-1])
    assert payload["policy_stage"] == recommendation.policy_stage
    assert payload["topic_id"] == recommendation.topic_id


def test_persistence_atomic_backup_and_corruption_fallback(tmp_path) -> None:
    path = tmp_path / "state.json"
    storage_files.write_json(path, {"schema_version": 3, "value": 1})
    storage_files.write_json(path, {"schema_version": 3, "value": 2})

    assert storage_files.backup_path(path).exists()

    path.write_text("{broken", encoding="utf-8")
    loaded = storage_files.read_json(path)

    assert loaded["value"] == 1


def test_schema_version_is_written_in_saved_course_state(tmp_path, monkeypatch) -> None:
    data_dir = _copy_seed_data(tmp_path)
    monkeypatch.setattr(storage_files, "USERS_DIR", data_dir / "users")

    course = storage_files.load_course_state("demo_user", "system-design")
    storage_files.save_course_state("demo_user", course)
    course_path = data_dir / "users" / "demo_user" / "course_state" / "system-design.json"
    raw = storage_files.read_json(course_path)

    assert raw["schema_version"] == 3
    assert raw["topics"][0]["priority_within_course"] >= 1


def test_onboarding_creates_course_pack_and_course_state(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    courses_dir = tmp_path / "courses"
    topics_file = tmp_path / "topics.json"
    topics_file.write_text(
        """
[
  {
    "id": "intro",
    "name": "Intro",
    "summary": "Start here.",
    "priority_within_course": 5,
    "prerequisites": [],
    "next_topics": ["deep-dive"],
    "starter": true,
    "review_weight": 1.2,
    "mode_preference": "either"
  },
  {
    "id": "deep-dive",
    "name": "Deep Dive",
    "summary": "Continue here.",
    "priority_within_course": 4,
    "prerequisites": ["intro"],
    "next_topics": [],
    "starter": false,
    "review_weight": 1.1,
    "mode_preference": "full"
  }
]
        """.strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(storage_files, "USERS_DIR", data_dir / "users")
    monkeypatch.setattr(storage_files, "COURSES_DIR", courses_dir)
    monkeypatch.setattr(onboarding, "COURSES_DIR", courses_dir)

    state = onboarding.create_local_course(
        user_id="solo-test",
        course_id="new-course",
        title="New Course",
        goal="Learn something useful",
        topics_file=topics_file,
        priority=4,
        sessions_per_week=2,
        target_minutes=20,
    )

    saved = storage_files.load_course_state("solo-test", "new-course")
    active = storage_files.load_active_courses("solo-test")

    assert state.course_id == "new-course"
    assert saved.topics[0].starter is True
    assert "new-course" in active.active_courses
    assert (courses_dir / "new-course" / "topics.json").exists()


def test_onboarded_course_is_immediately_recommendable(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    courses_dir = tmp_path / "courses"
    topics_file = tmp_path / "topics.json"
    topics_file.write_text(
        """
[
  {
    "id": "starter",
    "name": "Starter",
    "summary": "Start here.",
    "priority_within_course": 5,
    "prerequisites": [],
    "next_topics": ["later"],
    "starter": true,
    "review_weight": 1.2,
    "mode_preference": "either"
  },
  {
    "id": "later",
    "name": "Later",
    "summary": "Later topic.",
    "priority_within_course": 4,
    "prerequisites": ["starter"],
    "next_topics": [],
    "starter": false,
    "review_weight": 1.0,
    "mode_preference": "full"
  }
]
        """.strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(storage_files, "USERS_DIR", data_dir / "users")
    monkeypatch.setattr(storage_files, "COURSES_DIR", courses_dir)
    monkeypatch.setattr(onboarding, "COURSES_DIR", courses_dir)

    onboarding.create_local_course(
        user_id="solo-test",
        course_id="fresh-course",
        title="Fresh Course",
        goal="Goal",
        topics_file=topics_file,
    )

    recommendation = session_runner.recommend_for_today("solo-test", persist_audit=True)

    assert recommendation.topic_id == "starter"
    assert recommendation.policy_stage == "advancement"


def test_longitudinal_simulation_moves_from_consolidation_to_recovery_to_advancement() -> None:
    foundation = TopicState(
        id="foundation",
        name="Foundation",
        state="learning",
        mastery=0.6,
        confidence="medium",
        starter=True,
        priority_within_course=5,
        next_topics=["follow-up"],
        last_seen="2026-03-09",
        next_review="2026-03-10",
    )
    follow_up = TopicState(
        id="follow-up",
        name="Follow Up",
        state="unseen",
        mastery=0.05,
        confidence="low",
        prerequisites=["foundation"],
        priority_within_course=4,
    )
    course = _make_course(topics=[foundation, follow_up], priority=4)

    class FrozenDate(date):
        current = date(2026, 3, 10)

        @classmethod
        def today(cls):
            return cls.current

    review_bad = ReviewResult(
        score=0.35,
        what_was_right="Started it.",
        what_was_missing="Weak recall.",
        stronger_answer_guidance="Retry foundations.",
        weak_signals=["recall"],
        next_step="Retry tomorrow.",
        corrected_notes="Bad attempt.",
    )
    review_good = ReviewResult(
        score=0.9,
        what_was_right="Recovered well.",
        what_was_missing="Minor gaps.",
        stronger_answer_guidance="Move on.",
        weak_signals=[],
        next_step="Unlock the next topic.",
        corrected_notes="Good attempt.",
    )
    session = session_module.SessionRecord(
        session_id="sim-1",
        user_id="solo",
        course_id=course.course_id,
        topic_id="foundation",
        mode="full",
        policy_stage="consolidation",
        recommendation_reason="test",
        recommendation_breakdown=session_module.RecommendationBreakdown(),
        status="awaiting_answer",
        started_at="2026-03-10T00:00:00+00:00",
    )

    original_date = prioritizer.date
    try:
        prioritizer.date = FrozenDate
        day1 = prioritizer.choose_recommendation([course])
        assert day1.policy_stage == "consolidation"
        assert day1.topic_id == "foundation"

        course, session = rules.apply_session_completion(
            course,
            "foundation",
            session,
            review_bad,
            now=datetime(2026, 3, 10, tzinfo=UTC),
        )

        FrozenDate.current = date(2026, 3, 11)
        day2 = prioritizer.choose_recommendation([course])
        assert day2.policy_stage == "recovery"
        assert day2.topic_id == "foundation"

        session.session_id = "sim-2"
        session.status = "awaiting_answer"
        session.started_at = "2026-03-11T00:00:00+00:00"
        course, session = rules.apply_session_completion(
            course,
            "foundation",
            session,
            review_good,
            now=datetime(2026, 3, 11, tzinfo=UTC),
        )

        FrozenDate.current = date(2026, 3, 12)
        day3 = prioritizer.choose_recommendation([course])
        assert day3.policy_stage == "advancement"
        assert day3.topic_id == "follow-up"
    finally:
        prioritizer.date = original_date


def test_restart_does_not_double_count_scheduled_adherence_after_v3_policy_changes(
    tmp_path,
    monkeypatch,
) -> None:
    data_dir = _copy_seed_data(tmp_path)
    monkeypatch.setattr(storage_files, "USERS_DIR", data_dir / "users")

    class FakeLLM:
        def teach_concept(self, payload: str) -> str:
            return "teach"

        def generate_quiz(self, payload: str) -> str:
            return "quiz"

    user_id = storage_files.resolve_user_id_for_telegram(9191, "Solo User")
    first, _ = session_runner.start_session(user_id, FakeLLM())
    restarted, message = session_runner.start_session(user_id, FakeLLM(), action="restart")
    course = storage_files.load_course_state(user_id, first.course_id)

    assert restarted is not None
    assert restarted.session_id != first.session_id
    assert "without double-counting scheduled adherence" in message
    assert course.adherence.scheduled == 7
    assert course.adherence.abandoned == 1


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


def test_review_answer_falls_back_on_malformed_output(monkeypatch) -> None:
    class FakeResponses:
        def parse(self, **kwargs):
            raise RuntimeError("parse failed")

        def create(self, **kwargs):
            return SimpleNamespace(output_text="not json at all")

    def fake_openai(api_key):
        return SimpleNamespace(responses=FakeResponses())

    monkeypatch.setattr(llm_client_module, "OpenAI", fake_openai)
    settings = SimpleNamespace(openai_api_key="test-key", openai_model="gpt-5-mini")
    client = llm_client_module.LLMClient(settings)

    result = client.review_answer("payload")

    assert result.score == 0.5
    assert result.confidence == "low"
    assert result.weak_signals == ["structured recall"]


def test_checkin_summary_falls_back_on_connection_error(monkeypatch) -> None:
    class FakeResponses:
        def create(self, **kwargs):
            raise RuntimeError("connection error")

    def fake_openai(api_key):
        return SimpleNamespace(responses=FakeResponses())

    monkeypatch.setattr(llm_client_module, "OpenAI", fake_openai)
    settings = SimpleNamespace(openai_api_key="test-key", openai_model="gpt-5-mini")
    client = llm_client_module.LLMClient(settings)

    summary = client.run_checkin_summary("payload")

    assert "highest-priority course" in summary
