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
    limit = 10
    if len(context.args) > 1:
        await update.message.reply_text("Usage: /run_replay [limit]")
        return
    if context.args:
        try:
            limit = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Usage: /run_replay [limit]")
            return
    result = _service.run_replay_worker(limit=limit)
    await update.message.reply_text(result.message)
