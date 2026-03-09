from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.guards import is_allowed_user


def parse_single_id_arg(args: list[str]) -> int | None:
    if len(args) != 1:
        return None
    raw_value = args[0].strip()
    if not raw_value:
        return None
    try:
        parsed = int(raw_value)
    except ValueError:
        return None
    if parsed <= 0:
        return None
    return parsed


async def reject_if_unauthorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if is_allowed_user(update):
        return False
    if update.message:
        await update.message.reply_text("Unauthorized user.")
    return True
