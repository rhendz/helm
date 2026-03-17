---
estimated_steps: 6
estimated_files: 5
---

# T01: Define TaskSemantics model, approval policy stub, and LLM inference method

**Slice:** S01 — Task inference engine and `/task` quick-add
**Milestone:** M004

## Description

Establish the shared domain types and inference capability for the `/task` quick-add feature. This task adds three things: (1) a `TaskSemantics` Pydantic model and `WeeklyTaskRequest` field extensions in the orchestration schemas, (2) a `ConditionalApprovalPolicy` stub in a new `scheduling.py` module, and (3) an `infer_task_semantics()` method on `LLMClient` using OpenAI structured output. All are pure library additions with no runtime wiring — tested via unit tests with mocked LLM calls.

**Key constraints from research:**
- `TaskSemantics` must use `extra="ignore"` (not `extra="forbid"`) because it's a target for `responses.parse` and OpenAI may include extra fields
- `responses.parse` call signature: `self._client.responses.parse(model=..., instructions=<system_prompt>, input=<user_text>, text_format=TaskSemantics)` — result in `response.output_parsed`
- The `text_format` argument must be the class itself (`TaskSemantics`), not an instance
- Pattern proven in codebase at `apps/study-agent/app/llm/client.py:53`
- OpenAI SDK 2.26.0 is installed; `responses.parse` is available
- `WeeklyTaskRequest` currently uses `extra="forbid"` — new fields must have `None` defaults for backward compatibility

## Steps

1. **Add `TaskSemantics` to `packages/orchestration/src/helm_orchestration/schemas.py`:**
   ```python
   class TaskSemantics(BaseModel):
       model_config = ConfigDict(extra="ignore")  # NOT "forbid" — LLM may add fields
       urgency: str  # low / medium / high
       priority: str  # low / medium / high
       sizing_minutes: int
       confidence: float  # 0.0–1.0
   ```
   Place it after the existing `ApprovalAction` enum (it uses `ApprovalAction` indirectly via the policy). Note: `extra="ignore"` is deliberate — this model is the `text_format` target for `responses.parse`, and OpenAI structured output may include extra metadata fields.

2. **Extend `WeeklyTaskRequest` in the same file:** Add `urgency: str | None = None` and `confidence: float | None = None` to the existing `WeeklyTaskRequest` class. These fields have `None` defaults so all existing callers (`WeeklyTaskRequest(title=..., ...)`) continue to work unchanged.

3. **Create `packages/orchestration/src/helm_orchestration/scheduling.py`:**
   ```python
   from __future__ import annotations
   from typing import Protocol
   from helm_orchestration.schemas import ApprovalAction, ApprovalDecision, TaskSemantics

   class ApprovalPolicy(Protocol):
       def evaluate(self, semantics: TaskSemantics) -> ApprovalDecision: ...

   class ConditionalApprovalPolicy:
       """S01 stub: auto-approve high-confidence short tasks, ask otherwise.
       Full conflict/displacement logic lands in S02."""
       CONFIDENCE_THRESHOLD: float = 0.8
       MAX_AUTO_APPROVE_MINUTES: int = 120

       def evaluate(self, semantics: TaskSemantics) -> ApprovalDecision:
           if (semantics.confidence >= self.CONFIDENCE_THRESHOLD
               and semantics.sizing_minutes <= self.MAX_AUTO_APPROVE_MINUTES):
               return ApprovalDecision(
                   action=ApprovalAction.APPROVE,
                   actor="system:conditional_policy",
                   target_artifact_id=0,  # no artifact in S01 stub
               )
           return ApprovalDecision(
               action=ApprovalAction.REQUEST_REVISION,
               actor="system:conditional_policy",
               target_artifact_id=0,
               revision_feedback="Confidence or sizing outside auto-approve thresholds",
           )
   ```
   The `ApprovalDecision` schema already exists in `schemas.py` with the right shape. Use `target_artifact_id=0` as a sentinel for S01 since there's no real proposal artifact yet.

4. **Export new types from `packages/orchestration/src/helm_orchestration/__init__.py`:** Add imports and `__all__` entries for `TaskSemantics`, `ApprovalPolicy`, and `ConditionalApprovalPolicy`. Import `TaskSemantics` from `schemas` (it's already in the schemas import block) and the policy types from `scheduling`.

5. **Add `infer_task_semantics()` to `packages/llm/src/helm_llm/client.py`:**
   ```python
   from helm_orchestration.schemas import TaskSemantics

   # Inside LLMClient class:
   def infer_task_semantics(self, text: str, model: str | None = None) -> TaskSemantics:
       response = self._client.responses.parse(
           model=model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
           instructions=(
               "You are a task analysis assistant for a personal scheduling system. "
               "Analyze the following task description and infer:\n"
               "- urgency: how time-sensitive (low/medium/high)\n"
               "- priority: how important (low/medium/high)\n"
               "- sizing_minutes: estimated effort in minutes (integer)\n"
               "- confidence: how confident you are in these inferences (0.0 to 1.0)\n"
               "Be conservative with confidence — use <0.8 when the task is vague or ambiguous."
           ),
           input=text,
           text_format=TaskSemantics,
       )
       return response.output_parsed
   ```
   Note: `instructions` is the system prompt equivalent for `responses.parse`. `input` is the user text. `text_format` is the Pydantic class (not an instance). Result is in `response.output_parsed`.

6. **Write `tests/unit/test_task_inference.py`:**
   - Test `TaskSemantics` model validation: valid construction, extra fields ignored, confidence bounds
   - Test `ConditionalApprovalPolicy.evaluate()` with table-driven cases:
     - confidence=0.9, sizing=60 → APPROVE
     - confidence=0.7, sizing=60 → REQUEST_REVISION (low confidence)
     - confidence=0.9, sizing=180 → REQUEST_REVISION (too long)
     - confidence=0.5, sizing=180 → REQUEST_REVISION (both)
     - confidence=0.8, sizing=120 → APPROVE (exact thresholds)
     - confidence=0.79, sizing=120 → REQUEST_REVISION (just below confidence)
     - confidence=0.8, sizing=121 → REQUEST_REVISION (just above sizing)
   - Test `LLMClient.infer_task_semantics()` with monkeypatched OpenAI client: mock `responses.parse` to return a fake response with `output_parsed` set to a `TaskSemantics` instance; verify the method returns it correctly and passes the right arguments to the SDK.

## Must-Haves

- [ ] `TaskSemantics` Pydantic model with `extra="ignore"` config — importable from `helm_orchestration`
- [ ] `WeeklyTaskRequest` extended with `urgency` and `confidence` fields (backward-compatible `None` defaults)
- [ ] `ConditionalApprovalPolicy.evaluate()` returns APPROVE for confidence ≥ 0.8 + sizing ≤ 120, REQUEST_REVISION otherwise
- [ ] `LLMClient.infer_task_semantics(text)` calls `responses.parse` with correct arguments and returns `TaskSemantics`
- [ ] Unit tests cover approval policy edge cases (exact thresholds) and mocked inference call
- [ ] Existing test suite passes (no regressions from schema changes)

## Observability Impact

This task is pure library additions (no runtime wiring), so there are no new log entries or DB rows produced by T01 itself. However, the types defined here are the observable surface for downstream tasks:

- **`TaskSemantics`** is the structured output of `LLMClient.infer_task_semantics()` — future structlog entries in T02 will log `urgency`, `priority`, `sizing_minutes`, and `confidence` as structured fields.
- **`ConditionalApprovalPolicy`** produces `ApprovalDecision` values that will be logged (action + actor) in T02's background task handler.
- **Failure visibility:** If `infer_task_semantics()` raises (e.g. OpenAI API error), `response.output_parsed` will be `None` — callers must guard against this. T02 wraps the call in try/except and pushes a user-facing error message to the operator chat.
- **Inspection surface:** No DB changes in T01. In T02, `workflow_runs` rows with `workflow_type="task_quick_add"` become the durable record.

## Verification

- `cd /Users/ankush/git/helm/.gsd/worktrees/M004 && uv run --frozen --extra dev pytest tests/unit/test_task_inference.py -v` — all tests pass
- `cd /Users/ankush/git/helm/.gsd/worktrees/M004 && bash scripts/test.sh` — full suite passes (no regressions)
- `python -c "from helm_orchestration import TaskSemantics, ConditionalApprovalPolicy"` — imports succeed

## Inputs

- `packages/orchestration/src/helm_orchestration/schemas.py` — existing schema file; add `TaskSemantics` model and `WeeklyTaskRequest` fields
- `packages/orchestration/src/helm_orchestration/__init__.py` — existing exports; extend with new types
- `packages/llm/src/helm_llm/client.py` — existing `LLMClient` with `summarize()` method; add `infer_task_semantics()`
- `apps/study-agent/app/llm/client.py` — reference for `responses.parse` pattern (line 53); do NOT modify this file
- `tests/unit/test_workflow_telegram_commands.py` — reference for monkeypatch patterns in tests; do NOT modify this file

## Expected Output

- `packages/orchestration/src/helm_orchestration/schemas.py` — `TaskSemantics` model added; `WeeklyTaskRequest` extended
- `packages/orchestration/src/helm_orchestration/scheduling.py` — new file with `ApprovalPolicy` protocol and `ConditionalApprovalPolicy`
- `packages/orchestration/src/helm_orchestration/__init__.py` — exports updated
- `packages/llm/src/helm_llm/client.py` — `infer_task_semantics()` method added to `LLMClient`
- `tests/unit/test_task_inference.py` — new test file with passing unit tests
