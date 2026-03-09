from pydantic_settings import BaseSettings, SettingsConfigDict


def runtime_settings_config(**overrides: object) -> SettingsConfigDict:
    return SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        **overrides,
    )


class RuntimeSettings(BaseSettings):
    model_config = runtime_settings_config()


class RuntimeAppSettings(RuntimeSettings):
    app_env: str = "local"
    log_level: str = "INFO"
