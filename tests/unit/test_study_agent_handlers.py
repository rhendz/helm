from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path

import pytest

STUDY_AGENT_ROOT = Path(__file__).resolve().parents[2] / "apps" / "study-agent"
if str(STUDY_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDY_AGENT_ROOT))

config = importlib.import_module("app.config")
handlers = importlib.import_module("app.telegram.handlers")
main_module = importlib.import_module("app.main")
rules = importlib.import_module("app.engine.rules")
session_runner = importlib.import_module("app.engine.session_runner")
storage_files = importlib.import_module("app.storage.files")
session_module = importlib.import_module("app.schemas.session")
ReviewResult = session_module.ReviewResult


class DummyTelegramUser:
    def __init__(self, user_id: int = 1234, full_name: str = "Solo User") -> None:
        self.id = user_id
        self.full_name = full_name
        self.username = "solo"


class DummyMessage:
    def __init__(self) -> None:
        self.replies: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


class DummyUpdate:
    def __init__(self, user_id: int = 1234) -> None:
        self.message = DummyMessage()
        self.effective_user = DummyTelegramUser(user_id=user_id)


class DummyContext:
    def __init__(self, args: list[str] | None = None) -> None:
        self.args = args or []


class FakeLLM:
    def teach_concept(self, payload: str) -> str:
        assert "Mode:" in payload
        return "Teaching explanation"

    def generate_quiz(self, payload: str) -> str:
        assert "Rubric:" in payload
        return "1. Explain the core tradeoff."

    def review_answer(self, payload: str) -> ReviewResult:
        assert "User answer:" in payload
        return ReviewResult(
            score=0.7,
            what_was_right="You named the main concept.",
            what_was_missing="You skipped the main tradeoff.",
            stronger_answer_guidance="Add one example and one failure mode.",
            weak_signals=["tradeoff clarity"],
            next_step="Review this again in two days.",
            corrected_notes="Corrected notes go here.",
        )

    def run_checkin_summary(self, payload: str) -> str:
        assert "Adherence summary" in payload
        return "Focus on system design and lower Thai cadence slightly."


def _copy_seed_data(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    shutil.copytree(STUDY_AGENT_ROOT / "data", data_dir)
    return data_dir


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    data_dir = _copy_seed_data(tmp_path)
    monkeypatch.setattr(storage_files, "USERS_DIR", data_dir / "users")
    yield data_dir


def test_settings_load_local_env(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENAI_API_KEY=test-openai\nTELEGRAM_BOT_TOKEN=test-telegram\nOPENAI_MODEL=test-model\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "BASE_DIR", tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    settings = config.Settings()

    assert settings.openai_api_key == "test-openai"
    assert settings.telegram_bot_token == "test-telegram"
    assert settings.openai_model == "test-model"


def test_main_invokes_polling(monkeypatch) -> None:
    calls: list[str] = []

    class FakeSettings:
        telegram_bot_token = "token"

        def validate_for_bot(self) -> None:
            calls.append("validate")

    class FakeLLMClient:
        def __init__(self, settings) -> None:
            assert settings.telegram_bot_token == "token"
            calls.append("llm")

    class FakeApp:
        def run_polling(self) -> None:
            calls.append("poll")

    def fake_build_application(token: str, llm_client) -> FakeApp:
        assert token == "token"
        assert isinstance(llm_client, FakeLLMClient)
        calls.append("build")
        return FakeApp()

    monkeypatch.setattr(main_module, "Settings", FakeSettings)
    monkeypatch.setattr(main_module, "LLMClient", FakeLLMClient)
    monkeypatch.setattr(main_module, "build_application", fake_build_application)

    main_module.main()

    assert calls == ["validate", "llm", "build", "poll"]


@pytest.mark.asyncio
async def test_handlers_cover_core_v2_flow(isolated_state) -> None:
    llm = FakeLLM()
    update = DummyUpdate()

    await handlers.today_handler(update, DummyContext())
    assert "Breakdown:" in update.message.replies[0]
    assert "Stage:" in update.message.replies[0]
    assert "Winning factors:" in update.message.replies[0]
    user_id = storage_files.resolve_user_id_for_telegram(1234, "Solo User")
    assert user_id != config.DEFAULT_USER_ID

    start_update = DummyUpdate()
    start = handlers.start_session_handler(llm)
    await start(start_update, DummyContext())
    active = storage_files.load_active_session(user_id)
    assert active is not None
    assert active.status == "awaiting_answer"
    assert active.policy_stage in {"recovery", "consolidation", "advancement"}

    answer_update = DummyUpdate()
    answer = handlers.answer_handler(llm)
    await answer(answer_update, DummyContext(["sample", "answer"]))
    assert "Artifact:" in answer_update.message.replies[0]
    assert storage_files.load_active_session(user_id) is None
    artifact_path = Path(answer_update.message.replies[0].split("Artifact: ", 1)[1])
    artifact_text = artifact_path.read_text(encoding="utf-8")
    assert "Structured Residue" in artifact_text
    assert "Policy stage" in artifact_text

    miss_update = DummyUpdate()
    await handlers.miss_handler(miss_update, DummyContext(["Overslept"]))
    course = storage_files.load_course_state(user_id, "system-design")
    assert course.adherence.missed >= 3

    status_update = DummyUpdate()
    await handlers.status_handler(status_update, DummyContext())
    assert "Priority now:" in status_update.message.replies[0]
    assert "Pressure:" in status_update.message.replies[0]


@pytest.mark.asyncio
async def test_session_lifecycle_resume_restart_abandon_and_expire(isolated_state) -> None:
    llm = FakeLLM()
    user_id = storage_files.resolve_user_id_for_telegram(555, "Solo User")

    first, message = session_runner.start_session(user_id, llm)
    assert "fresh" in message.lower()
    second, message = session_runner.start_session(user_id, llm)
    assert second.session_id == first.session_id
    assert "resuming" in message.lower()
    resumed_record = storage_files.load_session_record(user_id, first.session_id)
    assert resumed_record.resume_count == 1
    assert resumed_record.expires_at == second.expires_at

    restarted, message = session_runner.start_session(user_id, llm, action="restart")
    assert restarted.session_id != first.session_id
    old_record = storage_files.load_session_record(user_id, first.session_id)
    assert old_record.status == "abandoned"

    none_session, message = session_runner.start_session(user_id, llm, action="abandon")
    assert none_session is None
    assert "Abandoned" in message

    fresh, _ = session_runner.start_session(user_id, llm)
    course_before_expire = storage_files.load_course_state(user_id, fresh.course_id)
    completed_before = (
        course_before_expire.adherence.completed_full
        + course_before_expire.adherence.completed_lite
    )
    active_path = storage_files.active_session_path(user_id)
    active_payload = storage_files.read_json(active_path)
    active_payload["expires_at"] = "2000-01-01T00:00:00+00:00"
    storage_files.write_json(active_path, active_payload)
    record_path = storage_files.session_json_path(user_id, fresh.session_id)
    record_payload = storage_files.read_json(record_path)
    record_payload["expires_at"] = "2000-01-01T00:00:00+00:00"
    storage_files.write_json(record_path, record_payload)

    active, record, error = session_runner.validate_active_session(user_id)
    assert active is None
    assert record is None
    assert "expired" in error.lower()
    expired_record = storage_files.load_session_record(user_id, fresh.session_id)
    assert expired_record.status == "expired"
    course = storage_files.load_course_state(user_id, fresh.course_id)
    completed_after = course.adherence.completed_full + course.adherence.completed_lite
    assert completed_after == completed_before


@pytest.mark.asyncio
async def test_answer_without_active_or_with_expired_session_is_clear(isolated_state) -> None:
    llm = FakeLLM()
    user_id = storage_files.resolve_user_id_for_telegram(777, "Solo User")
    update = DummyUpdate(user_id=777)
    answer = handlers.answer_handler(llm)

    await answer(update, DummyContext(["test"]))
    assert update.message.replies == ["No active session. Run /start_session first."]

    session, _ = session_runner.start_session(user_id, llm)
    active_path = storage_files.active_session_path(user_id)
    active_payload = storage_files.read_json(active_path)
    active_payload["expires_at"] = "2000-01-01T00:00:00+00:00"
    storage_files.write_json(active_path, active_payload)
    record_path = storage_files.session_json_path(user_id, session.session_id)
    record_payload = storage_files.read_json(record_path)
    record_payload["expires_at"] = "2000-01-01T00:00:00+00:00"
    storage_files.write_json(record_path, record_payload)

    expired_update = DummyUpdate(user_id=777)
    await answer(expired_update, DummyContext(["test"]))
    assert "expired" in expired_update.message.replies[0].lower()


@pytest.mark.asyncio
async def test_answer_rejects_invalid_session_state(isolated_state) -> None:
    llm = FakeLLM()
    user_id = storage_files.resolve_user_id_for_telegram(778, "Solo User")
    session, _ = session_runner.start_session(user_id, llm)
    record_path = storage_files.session_json_path(user_id, session.session_id)
    record_payload = storage_files.read_json(record_path)
    record_payload["status"] = "recommended"
    storage_files.write_json(record_path, record_payload)

    update = DummyUpdate(user_id=778)
    answer = handlers.answer_handler(llm)
    await answer(update, DummyContext(["test"]))

    assert "invalid state" in update.message.replies[0].lower()


@pytest.mark.asyncio
async def test_checkin_requires_explicit_apply(isolated_state) -> None:
    llm = FakeLLM()
    user_id = storage_files.resolve_user_id_for_telegram(999, "Solo User")
    checkin = handlers.checkin_handler(llm)

    start_update = DummyUpdate(user_id=999)
    await checkin(start_update, DummyContext())
    assert "Question 1" in start_update.message.replies[0]

    for response in [
        "System design feels like friction.",
        "Prioritize system design more and Thai less next week.",
        "Caching basics is shaky.",
        "Reduce cadence a bit.",
    ]:
        update = DummyUpdate(user_id=999)
        await checkin(update, DummyContext([response]))

    state = storage_files.load_active_checkin(user_id)
    assert state is not None
    assert state.status == "awaiting_approval"
    before = storage_files.load_course_state(user_id, "system-design").priority
    assert any(change.course_id == "system-design" for change in state.proposed_changes)

    apply_update = DummyUpdate(user_id=999)
    await checkin(apply_update, DummyContext(["apply"]))
    after = storage_files.load_course_state(user_id, "system-design").priority

    assert "Applied changes:" in apply_update.message.replies[0]
    assert after == before
    assert storage_files.load_active_checkin(user_id) is None


@pytest.mark.asyncio
async def test_status_reports_active_session_warning(isolated_state) -> None:
    llm = FakeLLM()
    user_id = storage_files.resolve_user_id_for_telegram(4242, "Solo User")
    session_runner.start_session(user_id, llm)
    update = DummyUpdate(user_id=4242)

    await handlers.status_handler(update, DummyContext())

    assert "Active session:" in update.message.replies[0]
    audit_dir = storage_files.user_dir(user_id) / "recommendations"
    assert list(audit_dir.glob("*.json"))


@pytest.mark.asyncio
async def test_corrupted_active_session_state_recovers_cleanly(isolated_state) -> None:
    llm = FakeLLM()
    user_id = storage_files.resolve_user_id_for_telegram(5151, "Solo User")
    session_runner.start_session(user_id, llm)
    active_path = storage_files.active_session_path(user_id)
    active_path.write_text("{broken", encoding="utf-8")

    resumed, message = session_runner.start_session(user_id, llm)

    assert resumed is not None
    assert "corrupted" in message.lower()
    update = DummyUpdate(user_id=5151)
    await handlers.status_handler(update, DummyContext())
    assert "Priority now:" in update.message.replies[0]


@pytest.mark.asyncio
async def test_miss_does_not_clear_active_session(isolated_state) -> None:
    llm = FakeLLM()
    user_id = storage_files.resolve_user_id_for_telegram(6161, "Solo User")
    session_runner.start_session(user_id, llm)
    update = DummyUpdate(user_id=6161)

    await handlers.miss_handler(update, DummyContext(["Still busy"]))

    active = storage_files.load_active_session(user_id)
    assert active is not None
    audit_dir = storage_files.user_dir(user_id) / "recommendations"
    assert list(audit_dir.glob("*.json"))
