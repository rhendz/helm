from __future__ import annotations

from typing import TypedDict

from helm_llm.contracts.base import PromptContract


class DailyDigestOutput(TypedDict, total=False):
    summary: str
    recommended_actions: list[str]
    must_do_today: list[str]


DAILY_DIGEST_CONTRACT = PromptContract(
    workflow="daily_digest",
    version="v1",
    system_prompt=(
        "You generate concise daily digests for Telegram delivery. "
        "Return only JSON matching the schema with practical action language."
    ),
    output_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary": {"type": "string"},
            "recommended_actions": {
                "type": "array",
                "items": {"type": "string"},
            },
            "must_do_today": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["summary", "recommended_actions", "must_do_today"],
    },
)
