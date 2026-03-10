from __future__ import annotations

from app.config import Settings
from app.llm.client import LLMClient
from app.telegram.bot import build_application


def main() -> None:
    settings = Settings()
    settings.validate_for_bot()
    llm_client = LLMClient(settings)
    application = build_application(settings.telegram_bot_token, llm_client)
    application.run_polling()


if __name__ == "__main__":
    main()
