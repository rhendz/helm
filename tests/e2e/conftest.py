"""E2E test configuration.

E2E tests run on the host machine against:
- Postgres at localhost:5432 (Docker port-forwarded)
- Google Calendar API (real credentials from GOOGLE_* env vars)

The DATABASE_URL in .env points at the Docker hostname 'postgres' which is
only resolvable inside the Docker network. Override it to localhost for host
execution.
"""
import os

import pytest

# Must happen before any helm_storage import touches the engine
_docker_url = "postgresql+psycopg://helm:helm@postgres:5432/helm"
_local_url = "postgresql+psycopg://helm:helm@localhost:5432/helm"

if os.getenv("DATABASE_URL", "") == _docker_url:
    os.environ["DATABASE_URL"] = _local_url

# ---------------------------------------------------------------------------
# E2E safety gates (D007)
# ---------------------------------------------------------------------------
_HELM_E2E = os.getenv("HELM_E2E", "").lower() == "true"
_CALENDAR_TEST_ID = os.getenv("HELM_CALENDAR_TEST_ID", "")


def pytest_collection_modifyitems(config, items):
    """Skip all E2E tests when HELM_E2E is not set."""
    if _HELM_E2E:
        return
    skip_marker = pytest.mark.skip(reason="HELM_E2E not set — skipping E2E tests")
    for item in items:
        item.add_marker(skip_marker)


def pytest_configure(config):
    """Fail fast if HELM_E2E is set but HELM_CALENDAR_TEST_ID is missing or 'primary'."""
    if not _HELM_E2E:
        return
    if not _CALENDAR_TEST_ID:
        pytest.exit("HELM_CALENDAR_TEST_ID must be set when HELM_E2E=true", returncode=1)
    if _CALENDAR_TEST_ID.lower() == "primary":
        pytest.exit("HELM_CALENDAR_TEST_ID must not be 'primary' — use a staging calendar ID", returncode=1)


@pytest.fixture(scope="session")
def e2e_calendar_id() -> str:
    """Return the staging calendar ID for E2E tests."""
    return _CALENDAR_TEST_ID
