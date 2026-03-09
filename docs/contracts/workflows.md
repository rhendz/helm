# Workflow Contract Scaffold

## Email triage workflow

Input: normalized inbound email message artifact.
Output:

- thread classification
- priority score
- action item (optional)
- draft reply (optional)
- digest item (optional)
- agent run log

## Daily digest workflow

Input:

- open action items
- top digest items
- pending drafts
- study priorities

Output:

- concise Telegram digest
- agent run log

Ranking/query contract (RHE-18):

- Query only durable artifacts from storage tables; no prompt-memory state.
- Source priority bands: `action_items` > `digest_items` > `draft_replies` > `learning_tasks`.
- Score is explicit and testable:
  - `score = source_base + priority_score - age_penalty`
  - `source_base`: action=65, digest=55, draft=50, study=45
  - `priority_score`: clamped 1..5 mapped to `(6-priority) * 9`
  - `age_penalty`: `3 * age_days`
- Filter out low-value noise with `MIN_DIGEST_SCORE = 50`.
- Return at most `MAX_DIGEST_ITEMS = 5` sorted by descending score.
- Formatter must produce concise, action-oriented Telegram text.

## Study ingest workflow

Input: manual notes/transcripts.
Output:

- study summary
- learning tasks
- knowledge gaps
- digest item (optional)
- agent run log
