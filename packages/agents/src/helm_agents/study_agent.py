from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ExtractedKnowledgeGap:
    topic: str
    description: str
    severity: int = 3


@dataclass(slots=True, frozen=True)
class ExtractedLearningTask:
    title: str
    description: str | None = None
    priority: int = 3
    related_gap_topic: str | None = None


@dataclass(slots=True, frozen=True)
class ExtractedDigestCandidate:
    title: str
    summary: str
    priority: int


@dataclass(slots=True, frozen=True)
class StudyExtraction:
    summary: str
    learning_tasks: list[ExtractedLearningTask]
    knowledge_gaps: list[ExtractedKnowledgeGap]
    digest_candidate: ExtractedDigestCandidate | None


def extract_study_artifacts(raw_text: str) -> StudyExtraction:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    summary = _extract_summary(lines=lines, fallback_text=raw_text)
    gaps = _extract_knowledge_gaps(lines)
    tasks = _extract_learning_tasks(lines)
    digest_candidate = _build_digest_candidate(gaps=gaps, summary=summary)

    # TODO(rhe-19): replace marker-based extraction with structured LLM parsing + confidence.
    return StudyExtraction(
        summary=summary,
        learning_tasks=tasks,
        knowledge_gaps=gaps,
        digest_candidate=digest_candidate,
    )


def _extract_summary(*, lines: list[str], fallback_text: str) -> str:
    if lines:
        compact = " ".join(lines[:2])
    else:
        compact = fallback_text.strip()
    if not compact:
        return "No study content provided."
    return compact[:400]


def _extract_knowledge_gaps(lines: list[str]) -> list[ExtractedKnowledgeGap]:
    gaps: list[ExtractedKnowledgeGap] = []
    for line in lines:
        lowered = line.lower()
        if lowered.startswith(("gap:", "weakness:", "struggle:", "confused:")):
            content = line.split(":", maxsplit=1)[1].strip()
            if not content:
                continue
            gaps.append(
                ExtractedKnowledgeGap(
                    topic=_derive_topic(content),
                    description=content,
                    severity=_infer_gap_severity(content),
                )
            )
    return gaps


def _extract_learning_tasks(lines: list[str]) -> list[ExtractedLearningTask]:
    tasks: list[ExtractedLearningTask] = []
    for line in lines:
        lowered = line.lower()
        if lowered.startswith(("task:", "todo:", "next:", "- [ ]")):
            content = line.split(":", maxsplit=1)[1].strip() if ":" in line else line[5:].strip()
            if not content:
                continue
            tasks.append(
                ExtractedLearningTask(
                    title=content[:120],
                    description=content,
                    priority=_infer_task_priority(content),
                    related_gap_topic=_extract_gap_hint(content),
                )
            )
    return tasks


def _build_digest_candidate(
    *, gaps: list[ExtractedKnowledgeGap], summary: str
) -> ExtractedDigestCandidate | None:
    if not gaps:
        return None
    top_gap = sorted(gaps, key=lambda gap: gap.severity)[0]
    if top_gap.severity > 2 and len(gaps) < 2:
        return None
    return ExtractedDigestCandidate(
        title=f"Study gap: {top_gap.topic}",
        summary=summary[:200],
        priority=min(top_gap.severity, 2),
    )


def _derive_topic(text: str) -> str:
    words = text.replace("-", " ").split()
    if not words:
        return "Unspecified topic"
    return " ".join(words[:4]).strip(".,").title()


def _infer_gap_severity(text: str) -> int:
    lowered = text.lower()
    if any(token in lowered for token in ("blocked", "can't", "cannot", "critical")):
        return 1
    if any(token in lowered for token in ("confused", "unclear", "struggle")):
        return 2
    return 3


def _infer_task_priority(text: str) -> int:
    lowered = text.lower()
    if any(token in lowered for token in ("today", "tonight", "urgent", "asap")):
        return 1
    if any(token in lowered for token in ("this week", "soon", "next")):
        return 2
    return 3


def _extract_gap_hint(text: str) -> str | None:
    lowered = text.lower()
    if "review " in lowered:
        return text[lowered.index("review ") + 7 :].strip(" .")
    return None
