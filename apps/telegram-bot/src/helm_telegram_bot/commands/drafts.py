from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import (
    _INVALID_ARG,
    parse_optional_choice_arg,
    reject_if_unauthorized,
)
from helm_telegram_bot.services.command_service import TelegramCommandService

_service = TelegramCommandService()

_ALLOWED_STATUSES = {"pending_user", "snoozed", "approved"}


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    approval_status = parse_optional_choice_arg(context.args, allowed=_ALLOWED_STATUSES)
    if approval_status is _INVALID_ARG:
        await update.message.reply_text("Usage: /drafts [pending_user|snoozed|approved]")
        return
    drafts = _service.list_pending_drafts(approval_status=approval_status)
    if not drafts:
        if approval_status is None:
            await update.message.reply_text("No pending drafts.")
        else:
            await update.message.reply_text(f"No drafts with status {approval_status}.")
        return
    title = "Pending drafts:" if approval_status is None else f"Drafts ({approval_status}):"
    lines = [title]
    for draft in drafts:
        preview = draft.draft_text.replace("\n", " ").strip()[:80]
        lines.append(f"{draft.id}: {draft.status} {preview}")
    if approval_status != "approved":
        lines.append("Use /approve <id> or /snooze <id>.")
    await update.message.reply_text("\n".join(lines))
