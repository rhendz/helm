"""Compatibility wrapper around the standalone Email Agent triage workflow."""

from email_agent.triage import (  # noqa: F401
    EmailTriageWorkflowResult,
    build_email_triage_graph,
    run_email_triage_workflow,
)
