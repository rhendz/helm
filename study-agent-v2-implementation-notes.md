# Study Agent V2 Implementation Notes

## What changed

- Replaced hard-coded `demo_user` command handling with real Telegram-user-backed local state directories.
- Added explicit session lifecycle state and recovery behavior for resume, restart, abandon, and expiration.
- Centralized important state mutation logic in `apps/study-agent/app/engine/rules.py`.
- Added recent topic performance history and expanded adherence accounting.
- Improved recommendation output with a deterministic score breakdown.
- Added safer persistence with atomic writes, `.bak` backups, and schema version fields.
- Changed weekly check-in to produce explicit proposed changes before applying them.

## Key design decisions

- Kept the product solo-user and local-first. Identity plumbing maps one real Telegram user to one local state directory, but does not add multi-tenant infrastructure.
- Kept the LLM out of core state mutation. The LLM still teaches, quizzes, critiques, and summarizes. Deterministic rules own state updates.
- Used structured outputs first for answer review, but still normalize parsed values because live model output was not fully trustworthy.
- Used restart-on-existing-session semantics through `/start_session` instead of adding a new recovery command.

## Small deviations from the V2 proposal

- Session recommendation explanations are still text-first, with a simple numeric breakdown rather than a richer explanation object.
- Check-in mutation parsing is still heuristic. It is more explicit and local than V1, but not a full intent parser.
- Persistence safety improved, but there is still no full migration framework beyond version tagging and compatibility defaults.

## Remaining limitations

- The app is still single-person, single-bot, and file-backed.
- Recommendation quality is better, but still a readable heuristic rather than a proven planner.
- Check-in proposals are explicit now, but they still depend on simple text matching rules.
- There is still no true onboarding flow or course authoring workflow beyond seeded files.
