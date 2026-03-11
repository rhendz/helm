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
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /job <job_name>")
        return
    item = _service.get_job_control(context.args[0])
    if item is None:
        await update.message.reply_text(f"Unknown job: {context.args[0]}.")
        return
    state = "paused" if item.paused else "active"
    lines = [f"Job {item.job_name}", f"Status: {state}", "List: /jobs"]
    if item.run_command:
        lines.append(f"Run: {item.run_command}")
    if item.note:
        lines.append(f"Note: {item.note}")
    await update.message.reply_text("\n".join(lines))
