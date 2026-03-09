# Night Runner Runbook

This repository uses a lock-protected wrapper script for unattended Codex runs.

## Files Involved

- `docs/runbooks/night-runner-prompt.md`
  - Single source of truth for night-runner behavior.
- `scripts/night-runner.sh`
  - Wrapper that applies lock protection, timeout, and logging.
- `scripts/install-night-runner-cron.sh` (fallback)
  - Optional cron installer if Codex Automation is not used.

## Lock Behavior

- Lock directory: `.night-runner.lock`
- On start, runner attempts to create lock directory.
- If lock already exists, runner exits cleanly without starting.
- Lock is always removed on process exit via `trap`, including interrupts/errors.

## Manual Run

From repo root:

```bash
bash ./scripts/night-runner.sh
```

Dry run:

```bash
./scripts/night-runner.sh --dry-run
```

## Environment Variables

- `PROMPT_FILE`
  - Default: `docs/runbooks/night-runner-prompt.md`
- `MAX_HOURS_PER_RUN`
  - Default: `4`
  - Enforced by wrapper watchdog timeout

Example:

```bash
MAX_HOURS_PER_RUN=6 PROMPT_FILE=docs/runbooks/night-runner-prompt.md bash ./scripts/night-runner.sh
```

## Log Paths

- Log directory: `.night-runner-logs/`
- Per-run log file:
  - `.night-runner-logs/night-runner-<UTC timestamp>.log`

## Codex Automation Prompt (Exact Text, Shared Across Helm + ankushp)

Use this as the automation prompt:

```text
Run the local repository night runner in the current workspace:
bash ./scripts/night-runner.sh

After completion, return:
1) completed issues
2) blocked issues
3) backlogged issues with unblock steps
4) retro summary
5) proposed next sprint issue list mapped to the repo’s source-of-truth spec
   - for helm: docs/internal/helm-v1.md
   - for ankushp: use the project’s primary product/runbook spec in that repo
6) live paid API call usage summary

If a run is already active (.night-runner.lock exists), report that and exit without overlap.
```

## Scheduler Note

Codex Automation is the primary scheduler.
Use `scripts/install-night-runner-cron.sh` only as fallback where automation scheduling is unavailable.
