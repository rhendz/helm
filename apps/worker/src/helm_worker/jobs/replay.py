from email_agent.replay_queue import run_replay_queue
from helm_runtime.email_agent import build_email_agent_runtime
from helm_storage.db import SessionLocal


def run(*, limit: int = 10) -> int:
    return run_replay_queue(
        limit=limit,
        session_factory=SessionLocal,
        runtime_factory=build_email_agent_runtime,
    )
