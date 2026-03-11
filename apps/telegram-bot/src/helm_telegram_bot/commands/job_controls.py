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
    if len(context.args) > 1 or (context.args and context.args[0] not in {"paused", "active"}):
        await update.message.reply_text("Usage: /job_controls [paused|active]")
        return
    items = _service.list_job_controls()
    mode = context.args[0] if context.args else None
    if mode == "paused":
        items = [item for item in items if item.paused]
    if mode == "active":
        items = [item for item in items if not item.paused]
    if not items:
        if mode == "paused":
            await update.message.reply_text("No paused jobs.")
            return
        if mode == "active":
            await update.message.reply_text("No active jobs.")
            return
        await update.message.reply_text("No job controls.")
        return
    if mode == "paused":
        lines = ["Paused jobs:"]
    elif mode == "active":
        lines = ["Active jobs:"]
    else:
        lines = ["Job controls:"]
    for item in items:
        state = "paused" if item.paused else "active"
        suffix_parts = []
        if item.run_command:
            suffix_parts.append(f"run={item.run_command}")
        if item.note:
            suffix_parts.append(item.note)
        suffix = ""
        if suffix_parts:
            suffix = f" ({'; '.join(suffix_parts)})"
        lines.append(f"{item.job_name}: {state}{suffix}")
    await update.message.reply_text("\n".join(lines))
