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
    email_config,
    followup,
    job_controls,
    needsreview_threads,
    pause_job,
    pause_replay,
    proposals,
    remind,
    replay_status,
    replays,
    reprocess_thread,
    requeue_replay,
    resolve,
    resolved_threads,
    resume_job,
    resume_replay,
    review,
    reviews,
    run_job,
    run_replay,
    send,
    set_email_timezone,
    set_followup_days,
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
    application.add_handler(CommandHandler("email_config", email_config.handle))
    application.add_handler(CommandHandler("job_controls", job_controls.handle))
    application.add_handler(CommandHandler("needsreview_threads", needsreview_threads.handle))
    application.add_handler(CommandHandler("pause_job", pause_job.handle))
    application.add_handler(CommandHandler("pause_replay", pause_replay.handle))
    application.add_handler(CommandHandler("proposals", proposals.handle))
    application.add_handler(CommandHandler("replay_status", replay_status.handle))
    application.add_handler(CommandHandler("replays", replays.handle))
    application.add_handler(CommandHandler("run_job", run_job.handle))
    application.add_handler(CommandHandler("run_replay", run_replay.handle))
    application.add_handler(CommandHandler("requeue_replay", requeue_replay.handle))
    application.add_handler(CommandHandler("reprocess_thread", reprocess_thread.handle))
    application.add_handler(CommandHandler("resume_job", resume_job.handle))
    application.add_handler(CommandHandler("resume_replay", resume_replay.handle))
    application.add_handler(CommandHandler("approve", approve.handle))
    application.add_handler(CommandHandler("done_task", done_task.handle))
    application.add_handler(CommandHandler("resolved_threads", resolved_threads.handle))
    application.add_handler(CommandHandler("send", send.handle))
    application.add_handler(CommandHandler("snooze", snooze.handle))
    application.add_handler(CommandHandler("remind", remind.handle))
    application.add_handler(CommandHandler("followup", followup.handle))
    application.add_handler(CommandHandler("resolve", resolve.handle))
    application.add_handler(CommandHandler("review", review.handle))
    application.add_handler(CommandHandler("reviews", reviews.handle))
    application.add_handler(CommandHandler("set_email_timezone", set_email_timezone.handle))
    application.add_handler(CommandHandler("set_followup_days", set_followup_days.handle))
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
