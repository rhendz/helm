from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import parse_single_id_arg, reject_if_unauthorized
from helm_telegram_bot.services.command_service import TelegramCommandService

_service = TelegramCommandService()


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    task_id = parse_single_id_arg(context.args)
    if task_id is None:
        await update.message.reply_text("Usage: /done_task <task_id>")
        return
    await update.message.reply_text(_service.complete_task(task_id).message)
