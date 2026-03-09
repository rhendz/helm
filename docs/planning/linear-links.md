# Linear Mapping

Canonical initiative + issue map for Helm V1 execution.

Note: This file records the initial seed snapshot. Team rename/prefix changes can
make issue identifiers differ over time. For current state, use:
`make linear-export` and read `docs/workstreams/linear-inbox.md`.

## Initiatives (Linear Projects)

- Helm V1: Foundation & Storage
  - https://linear.app/rhendz/project/helm-v1-foundation-and-storage-ff124873a0b4
- Helm V1: Email Triage Loop
  - https://linear.app/rhendz/project/helm-v1-email-triage-loop-eb315c33732c
- Helm V1: Telegram Action Surface
  - https://linear.app/rhendz/project/helm-v1-telegram-action-surface-e28bf62b1cb0
- Helm V1: Daily Digest
  - https://linear.app/rhendz/project/helm-v1-daily-digest-3e89bf07f2f7
- Helm V1: Study Loop
  - https://linear.app/rhendz/project/helm-v1-study-loop-51d4fb07cf26
- Helm V1: Reliability & Observability
  - https://linear.app/rhendz/project/helm-v1-reliability-and-observability-21cc9958978b

## Seed Issues

- RHE-12 Implement V1 SQLAlchemy entities + Alembic baseline migration
  - https://linear.app/rhendz/issue/RHE-12/implement-v1-sqlalchemy-entities-alembic-baseline-migration
- RHE-13 Add repository contracts for action_items, draft_replies, digest_items
  - https://linear.app/rhendz/issue/RHE-13/add-repository-contracts-for-action-items-draft-replies-digest-items
- RHE-14 Implement Gmail ingestion connector scaffold with normalization contract
  - https://linear.app/rhendz/issue/RHE-14/implement-gmail-ingestion-connector-scaffold-with-normalization
- RHE-15 Build email triage workflow scaffold in orchestration package
  - https://linear.app/rhendz/issue/RHE-15/build-email-triage-workflow-scaffold-in-orchestration-package
- RHE-16 Implement Telegram /actions and /drafts backed by storage queries
  - https://linear.app/rhendz/issue/RHE-16/implement-telegram-actions-and-drafts-backed-by-storage-queries
- RHE-17 Implement /approve <id> and /snooze <id> command flow
  - https://linear.app/rhendz/issue/RHE-17/implement-approve-id-and-snooze-id-command-flow
- RHE-18 Implement digest ranking query and generation contract
  - https://linear.app/rhendz/issue/RHE-18/implement-digest-ranking-query-and-generation-contract
- RHE-19 Implement manual study ingest pipeline and knowledge-gap artifact creation
  - https://linear.app/rhendz/issue/RHE-19/implement-manual-study-ingest-pipeline-and-knowledge-gap-artifact
- RHE-20 Persist agent_runs and expose failure visibility endpoint
  - https://linear.app/rhendz/issue/RHE-20/persist-agent-runs-and-expose-failure-visibility-endpoint
