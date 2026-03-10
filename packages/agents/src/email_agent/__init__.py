"""Standalone Email Agent core package.

Helm apps should treat this package as a client boundary rather than importing
Helm-specific orchestration or storage internals directly.
"""

from email_agent.query import (
    get_email_draft_detail,
    get_email_thread_detail,
    list_draft_transition_audits_for_draft,
    list_email_drafts,
    list_email_proposals,
    list_email_threads,
)
from email_agent.reminders import (
    ScheduledTaskCreateResult,
    complete_scheduled_task,
    create_thread_reminder,
    list_scheduled_tasks,
    list_thread_scheduled_tasks,
)
from email_agent.reprocess import ThreadReprocessResult, reprocess_email_thread
from email_agent.scheduling import ScheduledThreadTaskRunResult, run_due_scheduled_thread_tasks
from email_agent.seed import plan_seed_threads, summarize_seed_plan
from email_agent.triage import (
    EmailTriageWorkflowResult,
    build_email_triage_graph,
    process_inbound_email_message,
    run_email_triage_workflow,
)
from email_agent.types import EmailMessage

__all__ = [
    "EmailMessage",
    "EmailTriageWorkflowResult",
    "ScheduledTaskCreateResult",
    "ThreadReprocessResult",
    "ScheduledThreadTaskRunResult",
    "build_email_triage_graph",
    "complete_scheduled_task",
    "create_thread_reminder",
    "get_email_draft_detail",
    "get_email_thread_detail",
    "list_draft_transition_audits_for_draft",
    "list_scheduled_tasks",
    "reprocess_email_thread",
    "list_email_drafts",
    "list_email_proposals",
    "list_email_threads",
    "list_thread_scheduled_tasks",
    "process_inbound_email_message",
    "run_due_scheduled_thread_tasks",
    "run_email_triage_workflow",
    "plan_seed_threads",
    "summarize_seed_plan",
]
