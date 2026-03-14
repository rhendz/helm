---
version: 1

# Previous GPT config (commented out for quick swap-back)
# models:
#   research:
#     model: gpt-5-mini
#     fallbacks:
#       - gpt-4o-mini
#       - gpt-5
#   planning:
#     model: gpt-5
#     fallbacks:
#       - gpt-5-mini
#       - gpt-4o-mini
#   execution:
#     model: gpt-5-mini
#     fallbacks:
#       - gpt-4o-mini
#       - gpt-5
#   completion:
#     model: gpt-5-mini
#     fallbacks:
#       - gpt-5
#       - gpt-4o-mini
# auto_supervisor:
#   model: gpt-5-mini

models:
  research:
    model: claude-haiku-4-5
    fallbacks:
      - claude-sonnet-4-0
      - claude-3-haiku-20240307
  planning:
    model: claude-haiku-4-5
    fallbacks:
      - claude-sonnet-4-0
      - claude-3-7-sonnet-20250219
  execution:
    model: claude-haiku-4-5
    fallbacks:
      - claude-sonnet-4-0
      - claude-3-haiku-20240307
  completion:
    model: claude-haiku-4-5
    fallbacks:
      - claude-sonnet-4-0
      - claude-3-haiku-20240307

skill_discovery: suggest

auto_supervisor:
  model: claude-haiku-4-5
  soft_timeout_minutes: 20
  idle_timeout_minutes: 10
  hard_timeout_minutes: 30

budget_ceiling: 15.00

git:
  snapshots: true
  auto_push: false
  push_branches: false
---