from helm_observability.logging import get_logger

from helm_agents.digest_generation import build_digest_text
from helm_agents.digest_query import StorageDigestInputProvider


def build_daily_digest() -> str:
    logger = get_logger("helm_agents.digest")
    input_provider = StorageDigestInputProvider(limit_per_source=20)
    inputs = input_provider.fetch_inputs()
    digest_text = build_digest_text(inputs)
    logger.info(
        "build_daily_digest",
        open_actions=len(inputs.open_action_items),
        digest_items=len(inputs.top_digest_items),
        pending_drafts=len(inputs.pending_drafts),
        study_priorities=len(inputs.study_priorities),
    )
    return digest_text
