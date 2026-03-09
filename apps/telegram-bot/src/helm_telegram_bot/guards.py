from telegram import Update

from helm_telegram_bot.config import get_settings


def is_allowed_user(update: Update) -> bool:
    settings = get_settings()
    if settings.telegram_allowed_user_id is None:
        return True
    user = update.effective_user
    return bool(user and user.id == settings.telegram_allowed_user_id)
