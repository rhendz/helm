from __future__ import annotations

import json

from app.config import Settings
from app.schemas.session import ReviewResult
from app.storage.files import load_prompt
from openai import OpenAI


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        text = getattr(response, "output_text", "").strip()
        if text:
            return text
        return str(response)

    def teach_concept(self, payload: str) -> str:
        return self.complete(
            load_prompt("system.md") + "\n\n" + load_prompt("teacher.md"),
            payload,
        )

    def generate_quiz(self, payload: str) -> str:
        return self.complete(
            load_prompt("system.md") + "\n\n" + load_prompt("quizzer.md"),
            payload,
        )

    def review_answer(self, payload: str) -> ReviewResult:
        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=load_prompt("system.md") + "\n\n" + load_prompt("reviewer.md"),
                input=payload,
                text_format=ReviewResult,
            )
            if response.output_parsed is not None:
                return _normalize_review_result(response.output_parsed.model_dump())
        except Exception:
            pass

        raw = self.complete(
            load_prompt("system.md") + "\n\n" + load_prompt("reviewer.md"),
            payload,
        )
        try:
            parsed = json.loads(_extract_json(raw))
            return _normalize_review_result(parsed)
        except Exception:
            return ReviewResult(
                score=0.5,
                what_was_right="You attempted the topic and covered at least one relevant point.",
                what_was_missing=(
                    "The model response could not be parsed, so detailed feedback is limited."
                ),
                stronger_answer_guidance=(
                    "State the core concept, give one concrete example, "
                    "and name a tradeoff or common mistake."
                ),
                weak_signals=["structured recall"],
                next_step="Retry the same topic in lite mode tomorrow.",
                mastery_delta=0.0,
                confidence="low",
                corrected_notes=raw[:1200] if raw else "Review output was unavailable.",
            )

    def run_checkin_summary(self, payload: str) -> str:
        return self.complete(
            load_prompt("system.md") + "\n\n" + load_prompt("checkin.md"),
            payload,
        )


def _extract_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("{") and raw.endswith("}"):
        return raw
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in review output")
    parsed = json.loads(raw[start : end + 1])
    return json.dumps(parsed)


def _normalize_review_result(payload: dict) -> ReviewResult:
    score = payload.get("score", 0.5)
    if isinstance(score, (int, float)) and score > 1:
        score = float(score) / 10.0
    score = max(0.0, min(1.0, float(score)))

    mastery_delta = payload.get("mastery_delta", 0.0)
    mastery_delta = float(mastery_delta)
    if abs(mastery_delta) > 1:
        mastery_delta = mastery_delta / 10.0
    mastery_delta = max(-0.4, min(0.4, mastery_delta))

    weak_signals = payload.get("weak_signals", [])
    if isinstance(weak_signals, str):
        weak_signals = [item.strip() for item in weak_signals.split(",") if item.strip()]
        if not weak_signals:
            cleaned = payload["weak_signals"].strip()
            weak_signals = [cleaned] if cleaned else []

    confidence = payload.get("confidence", "medium")
    if isinstance(confidence, (int, float)):
        numeric = float(confidence)
        if numeric >= 0.75:
            confidence = "high"
        elif numeric >= 0.45:
            confidence = "medium"
        else:
            confidence = "low"
    confidence = str(confidence).lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "medium"

    return ReviewResult(
        score=score,
        what_was_right=str(payload.get("what_was_right", "")).strip(),
        what_was_missing=str(payload.get("what_was_missing", "")).strip(),
        stronger_answer_guidance=str(payload.get("stronger_answer_guidance", "")).strip(),
        weak_signals=weak_signals,
        next_step=str(payload.get("next_step", "")).strip(),
        mastery_delta=mastery_delta,
        confidence=confidence,
        corrected_notes=str(payload.get("corrected_notes", "")).strip(),
    )
