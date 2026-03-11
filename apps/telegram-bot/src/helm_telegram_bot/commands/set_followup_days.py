from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import reject_if_unauthorized
from helm_telegram_bot.services.command_service import TelegramCommandService

_service = TelegramCommandService()


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /set_followup_days <non-negative integer>")
        return
    try:
        value = int(context.args[0].strip())
    except ValueError:
        await update.message.reply_text("Usage: /set_followup_days <non-negative integer>")
        return
    result = _service.update_followup_days(value)
    await update.message.reply_text(result.message)
