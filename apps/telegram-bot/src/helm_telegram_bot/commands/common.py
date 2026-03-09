from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.guards import is_allowed_user


async def reject_if_unauthorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if is_allowed_user(update):
        return False
    if update.message:
        await update.message.reply_text("Unauthorized user.")
    return True
