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
session_runner = importlib.import_module("app.engine.session_runner")
storage_files = importlib.import_module("app.storage.files")
session_module = importlib.import_module("app.schemas.session")
ReviewResult = session_module.ReviewResult


class DummyMessage:
    def __init__(self) -> None:
        self.replies: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


class DummyUpdate:
    def __init__(self) -> None:
        self.message = DummyMessage()


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
            mastery_delta=0.1,
            confidence="medium",
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
async def test_handlers_cover_core_command_flow(isolated_state) -> None:
    llm = FakeLLM()

    today_update = DummyUpdate()
    await handlers.today_handler(today_update, DummyContext())
    assert "Course:" in today_update.message.replies[0]
    assert "Topic:" in today_update.message.replies[0]
    assert "Mode:" in today_update.message.replies[0]
    assert "Reason:" in today_update.message.replies[0]

    start_update = DummyUpdate()
    start = handlers.start_session_handler(llm)
    await start(start_update, DummyContext())
    active = storage_files.load_active_session(config.DEFAULT_USER_ID)
    assert active is not None
    assert len(start_update.message.replies) == 3
    assert start_update.message.replies[1].startswith("Teach:")
    assert start_update.message.replies[2].startswith("Quiz:")

    answer_update = DummyUpdate()
    answer = handlers.answer_handler(llm)
    await answer(answer_update, DummyContext(["A", "sample", "answer"]))
    assert "What was right:" in answer_update.message.replies[0]
    assert storage_files.load_active_session(config.DEFAULT_USER_ID) is None
    session_files = list((isolated_state / "users" / "demo_user" / "sessions").glob("*.md"))
    assert session_files

    miss_update = DummyUpdate()
    await handlers.miss_handler(miss_update, DummyContext(["Overslept"]))
    course = storage_files.load_course_state(config.DEFAULT_USER_ID, "system-design")
    assert course.adherence.missed >= 3
    assert course.adherence.recent_miss_reasons[-1] == "Overslept"
    assert "Miss recorded" in miss_update.message.replies[0]

    status_update = DummyUpdate()
    await handlers.status_handler(status_update, DummyContext())
    status_reply = status_update.message.replies[0]
    assert "Priority now:" in status_reply
    assert "Weakest:" in status_reply
    assert "Upcoming reviews:" in status_reply

    checkin = handlers.checkin_handler(llm)
    checkin_start = DummyUpdate()
    await checkin(checkin_start, DummyContext())
    assert "Weekly check-in started." in checkin_start.message.replies[0]

    for response in [
        "System design feels like friction.",
        "Prioritize system design more and Thai less next week.",
        "Caching basics is shakier than the JSON says.",
        "Reduce cadence a bit.",
    ]:
        checkin_update = DummyUpdate()
        await checkin(checkin_update, DummyContext([response]))

    weekly_dir = isolated_state / "users" / "demo_user" / "weekly_reviews"
    artifacts = list(weekly_dir.glob("*.md"))
    assert artifacts
    assert "Weekly check-in saved." in checkin_update.message.replies[0]


@pytest.mark.asyncio
async def test_answer_without_active_session_is_helpful(isolated_state) -> None:
    answer = handlers.answer_handler(FakeLLM())
    update = DummyUpdate()

    await answer(update, DummyContext(["test"]))

    assert update.message.replies == ["No active session. Run /start_session first."]
