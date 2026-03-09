from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import reject_if_unauthorized


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    # TODO(v1-phase4): return study priorities and latest gaps.
    await update.message.reply_text("Study view not implemented yet.")
