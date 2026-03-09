from __future__ import annotations

from typing import TypedDict

from helm_llm.contracts.base import PromptContract


class EmailTriageOutput(TypedDict, total=False):
    classification: str
    priority: str
    thread_summary: str
    action_item: str
    draft_reply: str
    should_create_digest_item: bool


EMAIL_TRIAGE_CONTRACT = PromptContract(
    workflow="email_triage",
    version="v1",
    system_prompt=(
        "You are an internal assistant for email triage. "
        "Return only JSON that matches the requested schema. "
        "Prefer concise, actionable fields."
    ),
    output_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "classification": {
                "type": "string",
                "enum": ["opportunity", "important", "routine", "noise"],
            },
            "priority": {"type": "string", "enum": ["high", "medium", "low"]},
            "thread_summary": {"type": "string"},
            "action_item": {"type": "string"},
            "draft_reply": {"type": "string"},
            "should_create_digest_item": {"type": "boolean"},
        },
        "required": [
            "classification",
            "priority",
            "thread_summary",
            "action_item",
            "should_create_digest_item",
        ],
    },
)
