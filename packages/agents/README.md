# package: agents

Purpose: workflow-specific business logic (classification, extraction, drafting, digesting).

Boundaries:

- Use storage + llm + domain abstractions.
- Emit durable artifacts; avoid hidden state.
- Keep agent-core packages callable without Helm app imports so Helm can act as a client/host.
