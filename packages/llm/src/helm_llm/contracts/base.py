from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from helm_llm.errors import LLMResponseFormatError


@dataclass(frozen=True)
class PromptContract:
    """Versioned contract that defines prompt instructions and output schema."""

    workflow: str
    version: str
    system_prompt: str
    output_schema: Mapping[str, Any]
    max_output_tokens: int = 1000

    @property
    def contract_id(self) -> str:
        return f"{self.workflow}_{self.version}"

    def render_user_input(self, payload: Mapping[str, Any]) -> str:
        """Render deterministic JSON payload for prompt input."""
        return json.dumps(payload, sort_keys=True, ensure_ascii=True)

    def parse_output(self, raw_text: str) -> dict[str, Any]:
        """Parse structured JSON output from model text response."""
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise LLMResponseFormatError("response is not valid JSON") from exc

        if not isinstance(parsed, dict):
            raise LLMResponseFormatError("response root must be a JSON object")
        return parsed
