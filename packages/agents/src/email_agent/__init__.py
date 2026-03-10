"""Standalone Email Agent core package.

Helm apps should treat this package as a client boundary rather than importing
Helm-specific orchestration or storage internals directly.
"""

from email_agent.query import list_email_drafts, list_email_proposals, list_email_threads
from email_agent.scheduling import ScheduledThreadTaskRunResult, run_due_scheduled_thread_tasks
from email_agent.triage import (
    EmailTriageWorkflowResult,
    build_email_triage_graph,
    run_email_triage_workflow,
)

__all__ = [
    "EmailTriageWorkflowResult",
    "ScheduledThreadTaskRunResult",
    "build_email_triage_graph",
    "list_email_drafts",
    "list_email_proposals",
    "list_email_threads",
    "run_due_scheduled_thread_tasks",
    "run_email_triage_workflow",
]
