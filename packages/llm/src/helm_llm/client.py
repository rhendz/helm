import os
from collections.abc import Mapping
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from helm_llm.contracts.base import PromptContract
from helm_llm.errors import LLMRequestError, LLMResponseFormatError, LLMTimeoutError


class LLMClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        default_model: str | None = None,
        timeout_seconds: float | None = None,
        openai_client: Any | None = None,
    ) -> None:
        resolved_api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._default_model = default_model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self._timeout_seconds = timeout_seconds or float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30"))

        if openai_client is not None:
            self._client = openai_client
            return

        if not resolved_api_key:
            raise RuntimeError("OPENAI_API_KEY is required")
        self._client = OpenAI(api_key=resolved_api_key, timeout=self._timeout_seconds)

    def summarize(self, text: str, model: str | None = None) -> str:
        response = self._create_response(
            model=model or self._default_model,
            instructions="Summarize the input in 3 concise bullets.",
            input=[{"role": "user", "content": text}],
            max_output_tokens=500,
        )
        return response.output_text

    def run_contract(
        self,
        contract: PromptContract,
        payload: Mapping[str, Any],
        *,
        model: str | None = None,
    ) -> dict[str, Any]:
        response = self._create_response(
            model=model or self._default_model,
            instructions=contract.system_prompt,
            input=[{"role": "user", "content": contract.render_user_input(payload)}],
            max_output_tokens=contract.max_output_tokens,
            text={
                "format": {
                    "type": "json_schema",
                    "name": contract.contract_id,
                    "strict": True,
                    "schema": contract.output_schema,
                }
            },
            metadata={"contract_id": contract.contract_id},
        )

        if not response.output_text:
            raise LLMResponseFormatError("model response did not include output_text")

        return contract.parse_output(response.output_text)

    def _create_response(self, **kwargs: Any) -> Any:
        # Artifact-driven execution: disable provider-side storage/memory for v1.
        kwargs.setdefault("store", False)
        kwargs.setdefault("timeout", self._timeout_seconds)
        try:
            return self._client.responses.create(**kwargs)
        except (APITimeoutError, TimeoutError) as exc:
            raise LLMTimeoutError("model request timed out") from exc
        except (APIConnectionError, APIStatusError) as exc:
            raise LLMRequestError("model request failed") from exc
        except Exception as exc:
            raise LLMRequestError("unexpected model request failure") from exc
