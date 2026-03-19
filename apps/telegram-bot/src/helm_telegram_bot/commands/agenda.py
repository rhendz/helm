"""Handler for /agenda command — shows today's calendar events."""
from datetime import datetime
from zoneinfo import ZoneInfo

from helm_observability.logging import get_logger
from helm_providers import GoogleCalendarProvider
from helm_storage.db import SessionLocal
from helm_storage.repositories.users import get_user_by_telegram_id
from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import reject_if_unauthorized
from helm_telegram_bot.config import get_settings

logger = get_logger("helm_telegram_bot.commands.agenda")


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return

    settings = get_settings()
    tz = ZoneInfo(settings.operator_timezone)

    telegram_user_id = update.effective_user.id
    with SessionLocal() as db:
        user = get_user_by_telegram_id(telegram_user_id, db)
        if user is None:
            await update.message.reply_text("No Helm user found for your Telegram account.")
            return
        provider = GoogleCalendarProvider(user.id, db)
        events = provider.list_today_events(
            calendar_id="primary",
            timezone=tz,
        )

    if not events:
        await update.message.reply_text("📅 No events today.")
        return

    lines = [f"📅 Today's agenda ({tz}):"]
    for event in events:
        summary = event.get("summary", "(no title)")
        start_raw = event.get("start", {}).get("dateTime")
        if start_raw:
            start_dt = datetime.fromisoformat(start_raw).astimezone(tz)
            time_str = start_dt.strftime("%-I:%M %p")
        else:
            time_str = "All day"
        lines.append(f"• {time_str} — {summary}")

    await update.message.reply_text("\n".join(lines))
