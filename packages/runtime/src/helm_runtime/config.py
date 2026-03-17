from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator
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
    operator_timezone: str  # required — no default; fails fast if unset or invalid

    @field_validator("operator_timezone")
    @classmethod
    def validate_operator_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, KeyError) as exc:
            raise ValueError(
                f"OPERATOR_TIMEZONE '{v}' is not a valid IANA timezone string. "
                f"Example: 'America/Los_Angeles'"
            ) from exc
        return v
