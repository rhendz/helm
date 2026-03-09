from functools import lru_cache

from helm_runtime import RuntimeAppSettings, runtime_settings_config


class BotSettings(RuntimeAppSettings):
    model_config = runtime_settings_config(env_ignore_empty=True)

    telegram_bot_token: str = ""
    telegram_allowed_user_id: int | None = None


@lru_cache
def get_settings() -> BotSettings:
    return BotSettings()
