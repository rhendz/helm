from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

LINEAR_API_URL = "https://api.linear.app/graphql"
LINEAR_REF_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")


@dataclass(slots=True)
class MergedPullRequest:
    number: int
    url: str
    title: str
    body: str
    merged_at: str
    merge_commit_sha: str


@dataclass(slots=True)
class LinearIssue:
    id: str
    identifier: str
    title: str
    state: str
    comments: list[str]
    url: str


@dataclass(slots=True)
class DriftFinding:
    issue_identifier: str
    pr_url: str
    merge_commit_sha: str
    problems: list[str]


@dataclass(slots=True)
class ReconcileResult:
    merged_prs: int
    linked_issues: int
    findings: list[DriftFinding]


def extract_linear_identifiers(text: str, *, team_key: str) -> set[str]:
    expected_prefix = f"{team_key.upper()}-"
    matches = {match.group(1).upper() for match in LINEAR_REF_PATTERN.finditer(text)}
    return {identifier for identifier in matches if identifier.startswith(expected_prefix)}


def analyze_drift(
    *,
    prs: list[MergedPullRequest],
    issues_by_identifier: dict[str, LinearIssue],
    team_key: str,
) -> ReconcileResult:
    findings: list[DriftFinding] = []
    linked_issues = 0
    for pr in prs:
        identifiers = extract_linear_identifiers(
            f"{pr.title}\n{pr.body}",
            team_key=team_key,
        )
        for identifier in sorted(identifiers):
            linked_issues += 1
            issue = issues_by_identifier.get(identifier)
            if issue is None:
                findings.append(
                    DriftFinding(
                        issue_identifier=identifier,
                        pr_url=pr.url,
                        merge_commit_sha=pr.merge_commit_sha,
                        problems=["issue_not_found_in_linear_team"],
                    )
                )
                continue

            problems: list[str] = []
            if issue.state.lower() != "done":
                problems.append(f"issue_not_done:{issue.state}")

            sha_present = any(pr.merge_commit_sha in comment for comment in issue.comments)
            if not sha_present:
                problems.append("missing_merge_sha_comment")

            if problems:
                findings.append(
                    DriftFinding(
                        issue_identifier=identifier,
                        pr_url=pr.url,
                        merge_commit_sha=pr.merge_commit_sha,
                        problems=problems,
                    )
                )
    return ReconcileResult(merged_prs=len(prs), linked_issues=linked_issues, findings=findings)


def fetch_merged_prs(*, since_days: int) -> list[MergedPullRequest]:
    since = (datetime.now(UTC) - timedelta(days=since_days)).date().isoformat()
    cmd = [
        "gh",
        "pr",
        "list",
        "--state",
        "merged",
        "--search",
        f"merged:>={since}",
        "--limit",
        "100",
        "--json",
        "number,url,title,body,mergedAt,mergeCommit",
    ]
    response = subprocess.run(cmd, check=True, capture_output=True, text=True)
    rows = json.loads(response.stdout)
    prs: list[MergedPullRequest] = []
    for row in rows:
        merge_commit = row.get("mergeCommit") or {}
        commit_sha = merge_commit.get("oid") or ""
        if not commit_sha:
            continue
        prs.append(
            MergedPullRequest(
                number=int(row["number"]),
                url=row["url"],
                title=row.get("title") or "",
                body=row.get("body") or "",
                merged_at=row.get("mergedAt") or "",
                merge_commit_sha=commit_sha,
            )
        )
    return prs


def fetch_team_issues(*, team_key: str) -> dict[str, LinearIssue]:
    team_id = resolve_team_id(team_key=team_key)
    query = """
    query($teamId: String!, $limit: Int!) {
      team(id: $teamId) {
        issues(first: $limit, orderBy: updatedAt) {
          nodes {
            id
            identifier
            title
            url
            state {
              name
            }
            comments(first: 50) {
              nodes {
                body
              }
            }
          }
        }
      }
    }
    """
    data = linear_request(query=query, variables={"teamId": team_id, "limit": 250})
    issues = data["team"]["issues"]["nodes"]
    by_identifier: dict[str, LinearIssue] = {}
    for issue in issues:
        identifier = (issue.get("identifier") or "").upper()
        comments = issue.get("comments", {}).get("nodes", [])
        by_identifier[identifier] = LinearIssue(
            id=issue["id"],
            identifier=identifier,
            title=issue.get("title") or "",
            state=(issue.get("state") or {}).get("name") or "Unknown",
            comments=[node.get("body") or "" for node in comments],
            url=issue.get("url") or "",
        )
    return by_identifier


def post_remediation_comment(*, issue_id: str, body: str) -> None:
    mutation = """
    mutation($input: CommentCreateInput!) {
      commentCreate(input: $input) {
        success
      }
    }
    """
    linear_request(query=mutation, variables={"input": {"issueId": issue_id, "body": body}})


def resolve_team_id(*, team_key: str) -> str:
    query = """
    query {
      teams(first: 100) {
        nodes {
          id
          key
        }
      }
    }
    """
    data = linear_request(query=query, variables={})
    wanted = team_key.upper()
    for team in data["teams"]["nodes"]:
        if (team.get("key") or "").upper() == wanted:
            return team["id"]
    raise RuntimeError(f"Linear team key not found: {team_key}")


def linear_request(*, query: str, variables: dict[str, Any]) -> dict[str, Any]:
    token = os.getenv("LINEAR_API_KEY", "")
    if not token:
        raise RuntimeError("LINEAR_API_KEY is required")
    payload = json.dumps({"query": query, "variables": variables}).encode()
    request = urllib.request.Request(
        LINEAR_API_URL,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": token},
    )
    with urllib.request.urlopen(request) as response:
        body = json.loads(response.read().decode())
    if body.get("errors"):
        raise RuntimeError(f"Linear API GraphQL errors: {body['errors']}")
    return body["data"]
