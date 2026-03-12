from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import parse_single_id_arg, reject_if_unauthorized
from helm_telegram_bot.commands.workflows import _format_run
from helm_telegram_bot.services.workflow_status_service import TelegramWorkflowStatusService

_service = TelegramWorkflowStatusService()


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await approve(update, context)


async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    run_id = parse_single_id_arg(context.args[:1])
    if run_id is None:
        await update.message.reply_text("Usage: /approve <run_id>")
        return
    result = _service.approve_run(run_id, actor=f"telegram:{update.effective_user.id}")
    await update.message.reply_text(_format_run(result))


async def reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    run_id = parse_single_id_arg(context.args[:1])
    if run_id is None:
        await update.message.reply_text("Usage: /reject <run_id>")
        return
    result = _service.reject_run(run_id, actor=f"telegram:{update.effective_user.id}")
    await update.message.reply_text(_format_run(result))


async def request_revision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    run_id = parse_single_id_arg(context.args[:1])
    feedback = " ".join(context.args[1:]).strip()
    if run_id is None or not feedback:
        await update.message.reply_text("Usage: /request_revision <run_id> <feedback>")
        return
    result = _service.request_revision(
        run_id,
        actor=f"telegram:{update.effective_user.id}",
        feedback=feedback,
    )
    await update.message.reply_text(_format_run(result))
