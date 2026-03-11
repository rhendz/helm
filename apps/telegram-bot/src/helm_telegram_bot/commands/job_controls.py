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
    items = _service.list_job_controls()
    if not items:
        await update.message.reply_text("No job controls.")
        return
    lines = ["Job controls:"]
    for item in items:
        state = "paused" if item.paused else "active"
        lines.append(f"{item.job_name}: {state}")
    await update.message.reply_text("\n".join(lines))
