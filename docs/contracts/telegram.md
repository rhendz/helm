# Telegram Command Contract Scaffold

Bootstrap commands:

- `/start`
- `/digest`
- `/actions`
- `/drafts`
- `/study`
- `/approve <id>`
- `/snooze <id>`

Rules:

- Responses should be concise and action-oriented.
- Outbound side effects require explicit user confirmation.
- Bot must enforce `TELEGRAM_ALLOWED_USER_ID` gate in V1.

