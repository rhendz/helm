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
    replay_id = parse_single_id_arg(context.args)
    if replay_id is None:
        await update.message.reply_text("Usage: /requeue_replay <replay_id>")
        return
    result = _service.requeue_replay_item(replay_id)
    await update.message.reply_text(result.message)
