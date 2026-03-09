from helm_runtime.pr_linear_reconcile import (
    LinearIssue,
    MergedPullRequest,
    analyze_drift,
    extract_linear_identifiers,
)


def test_extract_linear_identifiers_filters_to_team_prefix() -> None:
    text = "Implements HELM-35 and refs OTHER-10. Also helm-99 lowercase."
    identifiers = extract_linear_identifiers(text, team_key="HELM")
    assert identifiers == {"HELM-35"}


def test_analyze_drift_flags_missing_sha_comment_and_state() -> None:
    prs = [
        MergedPullRequest(
            number=99,
            url="https://github.com/rhendz/helm/pull/99",
            title="feat: test",
            body="Linear: HELM-35",
            merged_at="2026-03-09T00:00:00Z",
            merge_commit_sha="abc123",
        )
    ]
    issues_by_identifier = {
        "HELM-35": LinearIssue(
            id="issue-id",
            identifier="HELM-35",
            title="Test issue",
            state="In Progress",
            comments=["Night-runner verification without SHA"],
            url="https://linear.app/rhendz/issue/HELM-35",
        )
    }

    result = analyze_drift(
        prs=prs,
        issues_by_identifier=issues_by_identifier,
        team_key="HELM",
    )

    assert result.merged_prs == 1
    assert result.linked_issues == 1
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.issue_identifier == "HELM-35"
    assert "issue_not_done:In Progress" in finding.problems
    assert "missing_merge_sha_comment" in finding.problems


def test_analyze_drift_passes_when_done_and_sha_present() -> None:
    prs = [
        MergedPullRequest(
            number=100,
            url="https://github.com/rhendz/helm/pull/100",
            title="chore: test",
            body="Linear: HELM-40",
            merged_at="2026-03-09T00:00:00Z",
            merge_commit_sha="def456",
        )
    ]
    issues_by_identifier = {
        "HELM-40": LinearIssue(
            id="issue-id-2",
            identifier="HELM-40",
            title="Done issue",
            state="Done",
            comments=["Merged with SHA def456"],
            url="https://linear.app/rhendz/issue/HELM-40",
        )
    }

    result = analyze_drift(
        prs=prs,
        issues_by_identifier=issues_by_identifier,
        team_key="HELM",
    )

    assert result.findings == []

