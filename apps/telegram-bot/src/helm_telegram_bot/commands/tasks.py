from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import (
    _INVALID_ARG,
    parse_optional_choice_arg,
    reject_if_unauthorized,
)
from helm_telegram_bot.services.command_service import TelegramCommandService

_service = TelegramCommandService()
_ALLOWED_STATUSES = {"pending", "completed"}


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    status = parse_optional_choice_arg(context.args, allowed=_ALLOWED_STATUSES)
    if status is _INVALID_ARG:
        await update.message.reply_text("Usage: /tasks [pending|completed]")
        return
    resolved_status = "pending" if status is None else status
    tasks = _service.list_scheduled_tasks(status=resolved_status)
    if not tasks:
        await update.message.reply_text(f"No {resolved_status} email tasks.")
        return
    title = "Pending email tasks:" if resolved_status == "pending" else "Completed email tasks:"
    lines = [title]
    for task in tasks:
        due_at = task.due_at.isoformat().replace("+00:00", "Z")
        lines.append(f"{task.id}: thread {task.email_thread_id} {task.task_type} due {due_at}")
    await update.message.reply_text("\n".join(lines))
