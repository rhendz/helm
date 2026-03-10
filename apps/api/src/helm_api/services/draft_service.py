def list_drafts() -> list[dict]:
    from email_agent.adapters import build_helm_runtime
    from email_agent.query import list_email_drafts

    return [
        {
            "id": draft["id"],
            "channel_type": "email",
            "status": draft["approval_status"],
            "preview": draft["preview"],
            "is_stale": draft["approval_status"] == "snoozed",
        }
        for draft in list_email_drafts(runtime=build_helm_runtime())
        if draft["approval_status"] in {"pending_user", "snoozed"}
    ]


def requeue_stale_drafts(*, stale_after_hours: int, limit: int, dry_run: bool) -> dict:
    from email_agent.adapters import build_helm_runtime
    from email_agent.query import list_email_drafts

    runtime = build_helm_runtime()
    drafts = [
        draft
        for draft in list_email_drafts(limit=limit * 4, runtime=runtime)
        if draft["approval_status"] == "snoozed"
    ][:limit]
    draft_ids = [draft["id"] for draft in drafts]

    requeued_count = 0
    if not dry_run:
        for draft_id in draft_ids:
            if runtime.set_email_draft_approval_status(
                draft_id,
                approval_status="pending_user",
            ):
                requeued_count += 1

    return {
        "status": "accepted",
        "stale_after_hours": stale_after_hours,
        "dry_run": dry_run,
        "matched_count": len(draft_ids),
        "requeued_count": requeued_count,
        "draft_ids": draft_ids,
    }
