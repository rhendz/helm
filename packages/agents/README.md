# package: agents

Purpose: workflow-specific business logic (classification, drafting, digesting).

Boundaries:

- Use storage + llm + domain abstractions.
- Emit durable artifacts; avoid hidden state.
- Keep agent-core packages callable without Helm app imports so Helm can act as a client/host.

Packaging:

- `pyproject.toml` in this directory is the extraction-prep manifest for `email_agent`.
- Helm-specific runtime composition belongs under `helm_runtime`, not inside the `email_agent` package.
