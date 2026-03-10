from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import (
    _INVALID_ARG,
    parse_optional_choice_arg,
    reject_if_unauthorized,
)
from helm_telegram_bot.services.command_service import TelegramCommandService

_service = TelegramCommandService()
_ALLOWED_LABELS = {"Action", "Urgent", "NeedsReview"}


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    label = parse_optional_choice_arg(context.args, allowed=_ALLOWED_LABELS)
    if label in {None, _INVALID_ARG}:
        await update.message.reply_text("Usage: /threads_label <Action|Urgent|NeedsReview>")
        return
    threads = _service.list_threads(label=label)
    if not threads:
        await update.message.reply_text(f"No threads with label {label}.")
        return
    lines = [f"Threads ({label}):"]
    for thread in threads:
        summary = thread.current_summary or "(no summary)"
        lines.append(f"{thread.id}: {summary}")
    await update.message.reply_text("\n".join(lines))
