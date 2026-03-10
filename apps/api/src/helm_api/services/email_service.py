from email_agent.adapters import build_helm_runtime
from email_agent.query import list_email_drafts, list_email_proposals, list_email_threads


def _runtime():
    return build_helm_runtime()


def list_threads(*, limit: int = 20) -> list[dict]:
    return list_email_threads(limit=limit, runtime=_runtime())


def list_proposals(*, limit: int = 20) -> list[dict]:
    return list_email_proposals(limit=limit, runtime=_runtime())


def list_drafts(*, limit: int = 20) -> list[dict]:
    return list_email_drafts(limit=limit, runtime=_runtime())


__all__ = ["list_threads", "list_proposals", "list_drafts"]
