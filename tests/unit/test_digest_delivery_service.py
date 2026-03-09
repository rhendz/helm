import pytest
from helm_telegram_bot.services import digest_delivery


class _Settings:
    def __init__(self, *, token: str, user_id: int | None) -> None:
        self.telegram_bot_token = token
        self.telegram_allowed_user_id = user_id


def test_deliver_sends_message_with_configured_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        digest_delivery,
        "get_settings",
        lambda: _Settings(token="token-1", user_id=123),
    )
    seen: dict[str, object] = {}

    async def _send_message(*, token: str, chat_id: int, text: str) -> None:
        seen["token"] = token
        seen["chat_id"] = chat_id
        seen["text"] = text

    service = digest_delivery.TelegramDigestDeliveryService()
    monkeypatch.setattr(service, "_send_message", _send_message)

    service.deliver("Daily Brief")

    assert seen == {"token": "token-1", "chat_id": 123, "text": "Daily Brief"}


def test_deliver_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        digest_delivery,
        "get_settings",
        lambda: _Settings(token="", user_id=123),
    )
    service = digest_delivery.TelegramDigestDeliveryService()

    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        service.deliver("Daily Brief")


def test_deliver_requires_allowed_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        digest_delivery,
        "get_settings",
        lambda: _Settings(token="token-1", user_id=None),
    )
    service = digest_delivery.TelegramDigestDeliveryService()

    with pytest.raises(RuntimeError, match="TELEGRAM_ALLOWED_USER_ID"):
        service.deliver("Daily Brief")
