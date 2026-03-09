from __future__ import annotations

from typing import TypedDict

from helm_llm.contracts.base import PromptContract


class StudySummaryOutput(TypedDict, total=False):
    study_summary: str
    learning_tasks: list[str]
    knowledge_gaps: list[str]
    should_create_digest_item: bool


STUDY_SUMMARY_CONTRACT = PromptContract(
    workflow="study_summary",
    version="v1",
    system_prompt=(
        "You summarize study artifacts for durable tracking. "
        "Return only JSON matching the schema; avoid speculative detail."
    ),
    output_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "study_summary": {"type": "string"},
            "learning_tasks": {
                "type": "array",
                "items": {"type": "string"},
            },
            "knowledge_gaps": {
                "type": "array",
                "items": {"type": "string"},
            },
            "should_create_digest_item": {"type": "boolean"},
        },
        "required": [
            "study_summary",
            "learning_tasks",
            "knowledge_gaps",
            "should_create_digest_item",
        ],
    },
)
