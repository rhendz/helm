# package: orchestration

Purpose: coordinate multi-step agent workflows with explicit state transitions.

Boundaries:

- Define graph/state-machine behavior.
- Keep orchestration separate from connector and transport concerns.
- Agent-core logic should live in agent packages; Helm orchestration modules may wrap those cores for compatibility.
