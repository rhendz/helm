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
    threads = _service.list_needs_review_threads()
    if not threads:
        await update.message.reply_text("No NeedsReview threads.")
        return
    lines = ["NeedsReview threads:"]
    for thread in threads:
        summary = thread.current_summary or "(no summary)"
        lines.append(f"{thread.id}: {summary}")
    await update.message.reply_text("\n".join(lines))
