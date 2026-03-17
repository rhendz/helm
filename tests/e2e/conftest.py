"""E2E test configuration.

E2E tests run on the host machine against:
- Postgres at localhost:5432 (Docker port-forwarded)
- Google Calendar API (real credentials from GOOGLE_* env vars)

The DATABASE_URL in .env points at the Docker hostname 'postgres' which is
only resolvable inside the Docker network. Override it to localhost for host
execution.
"""
import os

# Must happen before any helm_storage import touches the engine
_docker_url = "postgresql+psycopg://helm:helm@postgres:5432/helm"
_local_url = "postgresql+psycopg://helm:helm@localhost:5432/helm"

if os.getenv("DATABASE_URL", "") == _docker_url:
    os.environ["DATABASE_URL"] = _local_url
