from telegram import Update
from telegram.ext import ContextTypes

from helm_agents.digest_agent import build_daily_digest
from helm_telegram_bot.commands.common import reject_if_unauthorized


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    text = build_daily_digest()
    await update.message.reply_text(text)
