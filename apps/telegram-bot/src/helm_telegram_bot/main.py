from helm_observability.logging import get_logger, setup_logging
from telegram.ext import Application, CommandHandler

from helm_telegram_bot.commands import (
    action_threads,
    actions,
    approve,
    digest,
    done_task,
    draft,
    drafts,
    followup,
    needsreview_threads,
    proposals,
    remind,
    reprocess_thread,
    resolve,
    resolved_threads,
    review,
    reviews,
    snooze,
    start,
    tasks,
    thread,
    threads,
    threads_label,
    uninitialized_threads,
    waiting_on_other_party_threads,
    waiting_on_user_threads,
)
from helm_telegram_bot.config import get_settings


def main() -> None:
    setup_logging()
    logger = get_logger("helm_telegram_bot")
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", start.handle))
    application.add_handler(CommandHandler("digest", digest.handle))
    application.add_handler(CommandHandler("action_threads", action_threads.handle))
    application.add_handler(CommandHandler("actions", actions.handle))
    application.add_handler(CommandHandler("draft", draft.handle))
    application.add_handler(CommandHandler("drafts", drafts.handle))
    application.add_handler(CommandHandler("needsreview_threads", needsreview_threads.handle))
    application.add_handler(CommandHandler("proposals", proposals.handle))
    application.add_handler(CommandHandler("reprocess_thread", reprocess_thread.handle))
    application.add_handler(CommandHandler("approve", approve.handle))
    application.add_handler(CommandHandler("done_task", done_task.handle))
    application.add_handler(CommandHandler("resolved_threads", resolved_threads.handle))
    application.add_handler(CommandHandler("snooze", snooze.handle))
    application.add_handler(CommandHandler("remind", remind.handle))
    application.add_handler(CommandHandler("followup", followup.handle))
    application.add_handler(CommandHandler("resolve", resolve.handle))
    application.add_handler(CommandHandler("review", review.handle))
    application.add_handler(CommandHandler("reviews", reviews.handle))
    application.add_handler(CommandHandler("tasks", tasks.handle))
    application.add_handler(CommandHandler("thread", thread.handle))
    application.add_handler(CommandHandler("threads", threads.handle))
    application.add_handler(CommandHandler("threads_label", threads_label.handle))
    application.add_handler(CommandHandler("uninitialized_threads", uninitialized_threads.handle))
    application.add_handler(
        CommandHandler("waiting_on_other_party_threads", waiting_on_other_party_threads.handle)
    )
    application.add_handler(
        CommandHandler("waiting_on_user_threads", waiting_on_user_threads.handle)
    )

    logger.info("telegram_bot_started")
    application.run_polling()


if __name__ == "__main__":
    main()
