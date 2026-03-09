from __future__ import annotations

import asyncio

from helm_observability.logging import get_logger
from telegram import Bot

from helm_telegram_bot.config import get_settings

logger = get_logger("helm_telegram_bot.services.digest_delivery")


class TelegramDigestDeliveryService:
    def deliver(self, text: str) -> None:
        settings = get_settings()
        token = settings.telegram_bot_token
        chat_id = settings.telegram_allowed_user_id

        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required for digest delivery.")
        if chat_id is None:
            raise RuntimeError("TELEGRAM_ALLOWED_USER_ID is required for digest delivery.")

        asyncio.run(self._send_message(token=token, chat_id=chat_id, text=text))
        logger.info("digest_delivered", chat_id=chat_id, text_chars=len(text))

    async def _send_message(self, *, token: str, chat_id: int, text: str) -> None:
        async with Bot(token=token) as bot:
            await bot.send_message(chat_id=chat_id, text=text)
