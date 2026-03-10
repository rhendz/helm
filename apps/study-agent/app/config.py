from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
PROMPTS_DIR = BASE_DIR / "prompts"
COURSES_DIR = BASE_DIR / "courses"
DATA_DIR = BASE_DIR / "data"
USERS_DIR = DATA_DIR / "users"
DEFAULT_USER_ID = "demo_user"
DEMO_TEMPLATE_USER_ID = "demo_user"
DEFAULT_MODEL = "gpt-5-mini"


def load_local_env() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


class Settings:
    def __init__(self) -> None:
        load_local_env()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.openai_model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

    def validate_for_bot(self) -> None:
        missing = []
        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        if not self.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Missing required environment variables: {joined}")
