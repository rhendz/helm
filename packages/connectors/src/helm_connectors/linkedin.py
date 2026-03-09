from typing import Any

from helm_observability.logging import get_logger


def pull_new_events(manual_payload: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    logger = get_logger("helm_connectors.linkedin")
    if manual_payload is not None:
        logger.info("linkedin_pull_manual_payload", count=len(manual_payload))
        # Scaffold mode: pass through explicit user-provided payload only.
        return manual_payload

    logger.info("linkedin_pull_stub_manual_mode")
    # TODO(v1-linkedin-feasibility): select ingestion path (official API vs defer).
    # TODO(v1-linkedin-manual-ingest): add explicit manual ingest contract + normalization.
    # TODO(v1-linkedin-go-no-go): enable only when criteria in docs/internal/linkedin-feasibility-v1.md are met.
    return []
