# package: llm

Purpose: OpenAI Responses API integration wrappers and prompt contracts.

Boundaries:

- Centralize model invocation and response parsing.
- Keep prompts versioned and testable.
- Keep provider-side memory disabled (`store=False`) so persisted artifacts remain source of truth.
