import os

from openai import OpenAI


class LLMClient:
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required")
        self._client = OpenAI(api_key=api_key)

    def summarize(self, text: str, model: str | None = None) -> str:
        # TODO(v1-phase2): replace with prompt contracts and structured outputs.
        response = self._client.responses.create(
            model=model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            input=[{"role": "user", "content": f"Summarize this text in 3 bullets:\n{text}"}],
        )
        return response.output_text
