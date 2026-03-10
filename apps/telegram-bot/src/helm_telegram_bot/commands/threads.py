from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import (
    _INVALID_ARG,
    parse_optional_choice_arg,
    reject_if_unauthorized,
)
from helm_telegram_bot.services.command_service import TelegramCommandService

_service = TelegramCommandService()
_ALLOWED_STATES = {
    "uninitialized",
    "waiting_on_user",
    "waiting_on_other_party",
    "needs_review",
    "resolved",
}


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    business_state = parse_optional_choice_arg(context.args, allowed=_ALLOWED_STATES)
    if business_state is _INVALID_ARG:
        await update.message.reply_text(
            "Usage: /threads "
            "[uninitialized|waiting_on_user|waiting_on_other_party|needs_review|resolved]"
        )
        return
    threads = _service.list_threads(business_state=business_state)
    if not threads:
        if business_state is None:
            await update.message.reply_text("No email threads found.")
        else:
            await update.message.reply_text(f"No threads with state {business_state}.")
        return
    title = "Email threads:" if business_state is None else f"Threads ({business_state}):"
    lines = [title]
    for thread in threads:
        summary = thread.current_summary or "(no summary)"
        lines.append(f"{thread.id}: {summary}")
    await update.message.reply_text("\n".join(lines))
