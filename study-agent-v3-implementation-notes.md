# Study Agent V3 Implementation Notes

## What changed

- Replaced the flat V2 recommendation heuristic with an explicit staged policy:
  - `recovery`
  - `consolidation`
  - `advancement`
- Expanded course/topic metadata and updated the seeded course packs to use:
  - `priority_within_course`
  - `prerequisites`
  - `next_topics`
  - `starter`
  - `review_weight`
  - `mode_preference`
  - `group`
- Added recommendation audit persistence under each user directory.
- Improved retention behavior with cooldown handling, repeated-failure resurfacing, and more selective consolidation.
- Added a lightweight local onboarding helper in `python -m app.onboarding`.
- Enriched session artifacts with structured recommendation and state-change residue.
- Added deterministic V3 tests for policy stages, progression, onboarding, audit output, and longitudinal behavior.

## Key design decisions

- Kept the deterministic rules engine as the owner of state mutation.
- Kept JSON as the operational source of truth and markdown as the readable residue layer.
- Stored course metadata in human-editable course-pack JSON and hydrated it into course state on load.
- Persisted compact recommendation audits as JSON instead of building a dashboard or analytics layer.
- Used a local CLI/helper for onboarding instead of expanding the Telegram bot surface.

## Small deviations from the V3 doc

- Recommendation audits are persisted as compact JSON files under the user directory rather than a separate markdown artifact.
- Status/debug visibility is improved through `/today`, `/status`, session artifacts, and audit files instead of adding a separate inspect command.

## Remaining limitations

- The recommendation policy is more trustworthy than V2, but it is still heuristic.
- Check-in proposal extraction is still deterministic text matching, not robust intent parsing.
- Onboarding creates a usable local course pack and course state, but it does not assess current mastery.
- There is still only one active study session and one active weekly check-in per user.
