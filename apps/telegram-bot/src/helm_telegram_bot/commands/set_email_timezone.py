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
    if len(context.args) != 1 or not context.args[0].strip():
        await update.message.reply_text("Usage: /set_email_timezone <IANA timezone>")
        return
    result = _service.update_email_timezone(context.args[0].strip())
    await update.message.reply_text(result.message)
