# package: agents

Purpose: workflow-specific business logic (classification, extraction, drafting, digesting).

Boundaries:

- Use storage + llm + domain abstractions.
- Emit durable artifacts; avoid hidden state.
