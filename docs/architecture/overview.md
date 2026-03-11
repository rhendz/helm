# Helm V1 Architecture Overview

Primary flow:

1. Connectors ingest external signals.
2. Agents classify/extract/summarize and generate artifacts.
3. Storage persists durable artifacts and run state in Postgres.
4. API and Telegram bot consume artifacts for user-facing actions.

Key rule: Postgres is the source of truth for system state.

TODO(v1-phase1): add sequence diagrams for email triage and digest flows.
