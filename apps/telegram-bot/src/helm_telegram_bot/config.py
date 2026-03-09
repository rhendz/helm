from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    telegram_bot_token: str = ""
    telegram_allowed_user_id: int | None = None


@lru_cache
def get_settings() -> BotSettings:
    return BotSettings()
