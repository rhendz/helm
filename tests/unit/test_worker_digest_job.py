import pytest
from helm_worker.jobs import digest


class _DigestResult:
    def __init__(self, text: str) -> None:
        self.text = text
        self.action_count = 2
        self.digest_item_count = 1
        self.pending_draft_count = 3


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
