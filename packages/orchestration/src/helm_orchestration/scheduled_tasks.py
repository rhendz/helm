"""Compatibility wrapper around standalone Email Agent scheduled-task logic."""

from email_agent.scheduling import (  # noqa: F401
    ScheduledThreadTaskRunResult,
    run_due_scheduled_thread_tasks,
)
