# Linear Intake Runbook

Use this runbook to pull current Linear work into a local, parallel-friendly inbox.

## Prerequisites

- `LINEAR_API_KEY` set in your shell or `.env`.
- Optional: `LINEAR_TEAM_KEY` (defaults to `RHE`).

## Commands

List projects:

```bash
python scripts/linear_intake.py list-projects
```

List issues (all):

```bash
python scripts/linear_intake.py list-issues
```

List issues by state:

```bash
python scripts/linear_intake.py list-issues --state "Backlog"
```

Generate local inbox snapshot:

```bash
python scripts/linear_intake.py export-md --output docs/workstreams/linear-inbox.md
```

## Notes

- This is read-only intake; it does not mutate Linear.
- Use filters (`--project`, `--state`, `--assignee`) to create low-conflict parallel picks.
