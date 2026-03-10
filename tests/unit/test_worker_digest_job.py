import pytest
from helm_worker.jobs import digest


@pytest.fixture(autouse=True)
def _default_no_recent_auto_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(digest, "_auto_delivery_recently_sent", lambda: False)


class _DigestResult:
    def __init__(self, text: str) -> None:
        self.text = text
        self.action_count = 2
        self.digest_item_count = 1
        self.pending_draft_count = 3
        self.stale_pending_draft_count = 0


def test_run_delivers_generated_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(digest, "generate_daily_digest", lambda: _DigestResult("Daily Brief"))
    seen: dict[str, str] = {}

    class _Service:
        def deliver(self, text: str) -> None:
            seen["text"] = text

    monkeypatch.setattr(digest, "_delivery_service", _Service())

    digest.run()

    assert seen == {"text": "Daily Brief"}


def test_run_raises_when_delivery_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(digest, "generate_daily_digest", lambda: _DigestResult("Daily Brief"))

    class _Service:
        def deliver(self, text: str) -> None:
            raise RuntimeError(f"send failed: {text}")

    monkeypatch.setattr(digest, "_delivery_service", _Service())

    with pytest.raises(RuntimeError, match="send failed"):
        digest.run()


def test_run_skips_delivery_when_no_signals(monkeypatch: pytest.MonkeyPatch) -> None:
    empty_digest = _DigestResult("Daily Brief")
    empty_digest.action_count = 0
    empty_digest.digest_item_count = 0
    empty_digest.pending_draft_count = 0
    seen: dict[str, str] = {}

    monkeypatch.setattr(digest, "generate_daily_digest", lambda: empty_digest)

    class _Service:
        def deliver(self, text: str) -> None:
            seen["text"] = text

    monkeypatch.setattr(digest, "_delivery_service", _Service())

    digest.run()

    assert seen == {}


def test_run_skips_delivery_when_interval_not_elapsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(digest, "_auto_delivery_recently_sent", lambda: True)
    seen: dict[str, str] = {}
    generated: dict[str, bool] = {"called": False}

    def _generate() -> _DigestResult:
        generated["called"] = True
        return _DigestResult("Daily Brief")

    class _Service:
        def deliver(self, text: str) -> None:
            seen["text"] = text

    monkeypatch.setattr(digest, "generate_daily_digest", _generate)
    monkeypatch.setattr(digest, "_delivery_service", _Service())

    digest.run()

    assert generated["called"] is False
    assert seen == {}
