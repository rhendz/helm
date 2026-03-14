---
version: 1
models:
  research:
    model: gpt-5-mini
    fallbacks:
      - gpt-4o-mini
      - gpt-5
  planning:
    model: gpt-5
    fallbacks:
      - gpt-5-mini
      - gpt-4o-mini
  execution:
    model: gpt-5-mini
    fallbacks:
      - gpt-4o-mini
      - gpt-5
  completion:
    model: gpt-5-mini
    fallbacks:
      - gpt-5
      - gpt-4o-mini
skill_discovery: suggest
auto_supervisor:
  model: gpt-5-mini
  soft_timeout_minutes: 20
  idle_timeout_minutes: 10
  hard_timeout_minutes: 30
budget_ceiling: 15.00
git:
  snapshots: true
  auto_push: false
  push_branches: false
---
