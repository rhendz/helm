import os

from helm_orchestration.schemas import TaskSemantics
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

    def infer_task_semantics(self, text: str, model: str | None = None) -> TaskSemantics:
        from datetime import date

        today = date.today().isoformat()
        response = self._client.responses.parse(
            model=model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            instructions=(
                "You are a task analysis assistant for a personal scheduling system. "
                f"Today's date is {today}. "
                "Analyze the following task description and infer:\n"
                "- urgency: how time-sensitive (low/medium/high)\n"
                "- priority: how important (low/medium/high)\n"
                "- sizing_minutes: estimated effort in minutes (integer)\n"
                "- confidence: how confident you are in these inferences (0.0 to 1.0)\n"
                "- suggested_date: the best date to schedule this task (ISO format YYYY-MM-DD). "
                "Infer from context clues like 'this week', 'tomorrow', 'by Wednesday', 'urgent', etc. "
                "If no timing context exists, suggest the next business day. "
                "Never suggest a date in the past.\n"
                "Be conservative with confidence — use <0.8 when the task is vague or ambiguous."
            ),
            input=text,
            text_format=TaskSemantics,
        )
        return response.output_parsed
