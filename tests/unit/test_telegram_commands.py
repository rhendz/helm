import pytest
from helm_telegram_bot.commands import approve, common, digest, snooze
from helm_telegram_bot.services.command_service import DraftTransitionResult


class _Message:
    def __init__(self) -> None:
        self.replies: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


class _Update:
    def __init__(self, *, user_id: int = 1) -> None:
        self.message = _Message()
        self.effective_user = type("User", (), {"id": user_id})()


class _Context:
    def __init__(self, args: list[str]) -> None:
        self.args = args


def test_parse_single_id_arg() -> None:
    assert common.parse_single_id_arg(["42"]) == 42
    assert common.parse_single_id_arg([]) is None
    assert common.parse_single_id_arg(["abc"]) is None
    assert common.parse_single_id_arg(["0"]) is None
    assert common.parse_single_id_arg(["1", "2"]) is None


@pytest.mark.asyncio
async def test_reject_if_unauthorized_replies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(common, "is_allowed_user", lambda _update: False)
    update = _Update()

    rejected = await common.reject_if_unauthorized(update, _Context(args=[]))

    assert rejected is True
    assert update.message.replies == ["Unauthorized user."]


@pytest.mark.asyncio
async def test_approve_usage_message_when_id_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(approve, "reject_if_unauthorized", _allow)
    update = _Update()

    await approve.handle(update, _Context(args=[]))

    assert update.message.replies == ["Usage: /approve <id>"]


@pytest.mark.asyncio
async def test_approve_parses_id_and_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def __init__(self) -> None:
            self.seen_id: int | None = None

        def approve_draft(self, draft_id: int) -> DraftTransitionResult:
            self.seen_id = draft_id
            return DraftTransitionResult(ok=True, message="Approved draft 7. Not sent yet.")

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    service = _Service()
    monkeypatch.setattr(approve, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(approve, "_service", service)
    update = _Update()

    await approve.handle(update, _Context(args=["7"]))

    assert service.seen_id == 7
    assert update.message.replies == ["Approved draft 7. Not sent yet."]


@pytest.mark.asyncio
async def test_approve_unauthorized_short_circuit(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def approve_draft(self, draft_id: int) -> DraftTransitionResult:
            raise AssertionError(f"service should not be called: {draft_id}")

    async def _deny(_update: _Update, _context: _Context) -> bool:
        return True

    monkeypatch.setattr(approve, "reject_if_unauthorized", _deny)
    monkeypatch.setattr(approve, "_service", _Service())
    update = _Update()

    await approve.handle(update, _Context(args=["9"]))

    assert update.message.replies == []


@pytest.mark.asyncio
async def test_snooze_usage_message_when_id_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(snooze, "reject_if_unauthorized", _allow)
    update = _Update()

    await snooze.handle(update, _Context(args=["oops"]))

    assert update.message.replies == ["Usage: /snooze <id>"]


@pytest.mark.asyncio
async def test_digest_command_replies_with_generated_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(digest, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(digest, "build_daily_digest", lambda: "Daily Brief\n1. Ship feature.")
    update = _Update()

    await digest.handle(update, _Context(args=[]))

    assert update.message.replies == ["Daily Brief\n1. Ship feature."]
