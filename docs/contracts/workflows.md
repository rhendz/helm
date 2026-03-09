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

## Study ingest workflow

Input: manual notes/transcripts.
Output:

- study summary
- learning tasks
- knowledge gaps
- digest item (optional)
- agent run log
