#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SRC = REPO_ROOT / "packages" / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconcile merged PRs against Linear issue state/comments."
    )
    parser.add_argument("--team", default="HELM", help="Linear team key (default: HELM)")
    parser.add_argument(
        "--since-days",
        type=int,
        default=14,
        help="Inspect merged PRs newer than this many days (default: 14)",
    )
    parser.add_argument(
        "--post-remediation-comments",
        action="store_true",
        help="Post remediation comments to referenced issues with detected drift.",
    )
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="Exit non-zero when drift is detected.",
    )
    return parser.parse_args()


def main() -> int:
    from helm_runtime.pr_linear_reconcile import (
        analyze_drift,
        fetch_merged_prs,
        fetch_team_issues,
        post_remediation_comment,
    )

    args = parse_args()
    if args.since_days < 1:
        print("error: --since-days must be >= 1", file=sys.stderr)
        return 2

    prs = fetch_merged_prs(since_days=args.since_days)
    issues_by_identifier = fetch_team_issues(team_key=args.team)
    result = analyze_drift(
        prs=prs,
        issues_by_identifier=issues_by_identifier,
        team_key=args.team,
    )

    print(
        f"reconcile_summary merged_prs={result.merged_prs} "
        f"linked_issues={result.linked_issues} drift_count={len(result.findings)}"
    )
    for finding in result.findings:
        problems = ",".join(finding.problems)
        print(
            f"drift issue={finding.issue_identifier} sha={finding.merge_commit_sha} "
            f"pr={finding.pr_url} problems={problems}"
        )

        if not args.post_remediation_comments:
            continue

        issue = issues_by_identifier.get(finding.issue_identifier)
        if issue is None:
            continue
        body = (
            "PR-to-Linear reconciliation detected drift:\n"
            f"- PR: {finding.pr_url}\n"
            f"- Merge commit: {finding.merge_commit_sha}\n"
            f"- Problems: {', '.join(finding.problems)}\n"
            "- Action: verify state/comment evidence and update if needed."
        )
        post_remediation_comment(issue_id=issue.id, body=body)

    if args.fail_on_drift and result.findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
