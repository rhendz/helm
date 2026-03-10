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
    if len(context.args) not in {1, 2}:
        await update.message.reply_text("Usage: /reprocess_thread <thread_id> [execute]")
        return
    thread_id = parse_single_id_arg([context.args[0]])
    if thread_id is None:
        await update.message.reply_text("Usage: /reprocess_thread <thread_id> [execute]")
        return
    dry_run = True
    if len(context.args) == 2:
        if context.args[1] != "execute":
            await update.message.reply_text("Usage: /reprocess_thread <thread_id> [execute]")
            return
        dry_run = False
    result = _service.reprocess_thread(thread_id, dry_run=dry_run)
    await update.message.reply_text(result.message)
