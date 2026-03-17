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
    # Research requires architectural judgment — haiku misses non-obvious patterns
    model: claude-sonnet-4-6
    fallbacks:
      - claude-opus-4-6
      - claude-3-7-sonnet-20250219

  planning:
    # Planning is the highest-stakes phase — use the strongest model available
    model: claude-opus-4-6
    fallbacks:
      - claude-sonnet-4-6
      - claude-3-7-sonnet-20250219

  execution:
    # Sonnet is the right execution tier; haiku fallback removed (quality cliff)
    model: claude-sonnet-4-6
    fallbacks:
      - claude-opus-4-6
      - claude-3-7-sonnet-20250219

  completion:
    # Summaries inform future slices — haiku fallback produces shallow output
    model: claude-sonnet-4-6
    fallbacks:
      - claude-opus-4-6
      - claude-3-7-sonnet-20250219

skill_discovery: suggest

auto_supervisor:
  # Supervisor is the quality gate for mid-run decisions — needs judgment capability
  model: claude-sonnet-4-6
  soft_timeout_minutes: 30
  idle_timeout_minutes: 15
  hard_timeout_minutes: 60

budget_ceiling: 100.00

git:
  snapshots: true
  auto_push: false
  push_branches: false
---
