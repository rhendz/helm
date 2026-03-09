def extract_study_artifacts(raw_text: str) -> dict:
    # TODO(v1-phase4, owner:packages/agents): replace heuristics with
    # validated LLM structured extraction.
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    summary = _build_summary(lines, raw_text)
    knowledge_gaps = _extract_knowledge_gaps(lines)
    learning_tasks = _extract_learning_tasks(lines, knowledge_gaps)
    return {"summary": summary, "knowledge_gaps": knowledge_gaps, "learning_tasks": learning_tasks}


def _build_summary(lines: list[str], raw_text: str) -> str:
    if not lines:
        return "No study notes provided."
    candidate = " ".join(lines[:3])
    if len(candidate) <= 280:
        return candidate
    trimmed = raw_text.strip().replace("\n", " ")
    return f"{trimmed[:277]}..." if len(trimmed) > 280 else trimmed


def _extract_knowledge_gaps(lines: list[str]) -> list[dict]:
    gaps: list[dict] = []
    for line in lines:
        lowered = line.lower()
        if _is_gap_line(lowered):
            description = _normalize_prefix(line)
            topic = _extract_topic(description)
            gaps.append(
                {
                    "topic": topic,
                    "description": description,
                    "severity": _infer_gap_severity(lowered),
                }
            )
    return gaps


def _extract_learning_tasks(lines: list[str], gaps: list[dict]) -> list[dict]:
    tasks: list[dict] = []
    for line in lines:
        lowered = line.lower()
        if _is_task_line(lowered):
            task_text = _normalize_prefix(line)
            tasks.append(
                {
                    "title": _truncate(task_text, 255),
                    "description": task_text,
                    "priority": _infer_task_priority(lowered),
                    "status": "open",
                    "related_gap_index": _match_related_gap(task_text, gaps),
                }
            )
    return tasks


def _is_gap_line(lowered_line: str) -> bool:
    return lowered_line.startswith(("gap:", "weakness:", "don't know", "struggle", "confused"))


def _is_task_line(lowered_line: str) -> bool:
    return lowered_line.startswith(("todo:", "task:", "next:", "- [ ]", "review:", "practice:"))


def _normalize_prefix(line: str) -> str:
    prefixes = ("gap:", "weakness:", "todo:", "task:", "next:", "review:", "practice:")
    cleaned = line.strip()
    if cleaned.startswith("- [ ]"):
        return cleaned.removeprefix("- [ ]").strip()
    lowered = cleaned.lower()
    for prefix in prefixes:
        if lowered.startswith(prefix):
            return cleaned[len(prefix) :].strip()
    return cleaned


def _extract_topic(description: str) -> str:
    topic = description.split(".")[0].split(",")[0].strip()
    return _truncate(topic or "unknown-topic", 255)


def _infer_gap_severity(lowered_line: str) -> str:
    if any(token in lowered_line for token in ("blocked", "can't", "cannot", "failed")):
        return "high"
    if any(token in lowered_line for token in ("struggle", "confused", "weak", "unclear")):
        return "medium"
    return "low"


def _infer_task_priority(lowered_line: str) -> int:
    if "urgent" in lowered_line or "today" in lowered_line:
        return 1
    if "tomorrow" in lowered_line or "soon" in lowered_line:
        return 2
    return 3


def _match_related_gap(task_text: str, gaps: list[dict]) -> int | None:
    lowered_task = task_text.lower()
    for gap_index, gap in enumerate(gaps):
        if gap["topic"].lower() in lowered_task:
            return gap_index
    return None


def _truncate(value: str, length: int) -> str:
    return value if len(value) <= length else value[: length - 3] + "..."
