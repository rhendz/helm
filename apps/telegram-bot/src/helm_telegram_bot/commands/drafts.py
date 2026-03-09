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
    drafts = _service.list_pending_drafts()
    if not drafts:
        await update.message.reply_text("No pending drafts.")
        return
    lines = ["Pending drafts:"]
    for draft in drafts:
        preview = draft.draft_text.replace("\n", " ").strip()[:80]
        lines.append(f"{draft.id}: {draft.status} {preview}")
    lines.append("Use /approve <id> or /snooze <id>.")
    await update.message.reply_text("\n".join(lines))
