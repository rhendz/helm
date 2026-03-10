from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import parse_single_id_arg, reject_if_unauthorized
from helm_telegram_bot.services.command_service import TelegramCommandService

_service = TelegramCommandService()


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    thread_id = parse_single_id_arg(context.args)
    if thread_id is None:
        await update.message.reply_text("Usage: /thread <thread_id>")
        return
    thread = _service.get_thread_detail(thread_id)
    if thread is None:
        await update.message.reply_text(f"Thread {thread_id} not found.")
        return
    labels = ", ".join(thread.visible_labels) if thread.visible_labels else "(none)"
    summary = thread.current_summary or "(no summary)"
    reason = thread.action_reason or "(none)"
    await update.message.reply_text(
        "\n".join(
            [
                f"Thread {thread.id}",
                f"State: {thread.business_state}",
                f"Labels: {labels}",
                f"Reason: {reason}",
                f"Summary: {summary}",
            ]
        )
    )
