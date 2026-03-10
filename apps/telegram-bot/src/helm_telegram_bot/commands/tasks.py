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
    tasks = _service.list_scheduled_tasks()
    if not tasks:
        await update.message.reply_text("No pending email tasks.")
        return
    lines = ["Pending email tasks:"]
    for task in tasks:
        due_at = task.due_at.isoformat().replace("+00:00", "Z")
        lines.append(f"{task.id}: thread {task.email_thread_id} {task.task_type} due {due_at}")
    await update.message.reply_text("\n".join(lines))
