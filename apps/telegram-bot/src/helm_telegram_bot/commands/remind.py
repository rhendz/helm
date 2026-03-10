from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import (
    parse_iso_datetime_arg,
    parse_two_arg_task_inputs,
    reject_if_unauthorized,
)
from helm_telegram_bot.services.command_service import TelegramCommandService

_service = TelegramCommandService()


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    parsed = parse_two_arg_task_inputs(context.args)
    if parsed is None:
        await update.message.reply_text("Usage: /remind <thread_id> <ISO8601>")
        return
    thread_id, due_at_raw = parsed
    due_at = parse_iso_datetime_arg(due_at_raw)
    if due_at is None:
        await update.message.reply_text("Usage: /remind <thread_id> <ISO8601>")
        return
    result = _service.create_thread_task(
        thread_id=thread_id,
        due_at=due_at,
        task_type="reminder",
    )
    await update.message.reply_text(result.message)
