# Testing Patterns

## Current Test Strategy

The repository is test-first at the unit and service-boundary level, but still light on deep integration coverage. The default test command is `scripts/test.sh`, which runs `uv run --frozen --extra dev pytest`. Pytest is configured in `pyproject.toml` with `testpaths = ["tests"]`, `addopts = "-q"`, and `asyncio_mode = "auto"`.

## Coverage Shape

- Unit tests are the primary quality mechanism. Most files under `tests/unit/` exercise one module or one repository at a time.
- Integration coverage exists but is shallow. `tests/integration/test_routes.py` verifies route availability and basic response shapes, while `tests/integration/test_scaffold.py` is still a placeholder with a documented TODO.
- There is no evidence of browser, Dockerized, or end-to-end workflow tests in the current tree, despite runbook guidance that those checks matter for merge readiness.

## Common Unit Test Patterns

### In-memory database tests

- Storage and service tests commonly create an in-memory SQLite engine with `create_engine("sqlite+pysqlite:///:memory:")`.
- They initialize schema with `Base.metadata.create_all(engine)` from `packages/storage/src/helm_storage/db.py`.
- Sessions are created inline with `Session(engine)` or `sessionmaker(...)`, not through global fixtures.
- Representative files: `tests/unit/test_storage_repositories.py`, `tests/unit/test_email_service.py`, `tests/unit/test_study_ingest_repository.py`.

This pattern keeps tests hermetic and fast, and it aligns with the repo rule to avoid external service dependencies in unit tests.

### Monkeypatch at import seams

- Service and worker tests heavily use `monkeypatch` to replace collaborators created inside the module under test.
- Examples:
  - `tests/unit/test_telegram_command_service.py` patches `build_helm_runtime`, `approve_draft`, `snooze_draft`, and list helpers inside `apps/telegram-bot/src/helm_telegram_bot/services/command_service.py`.
  - `tests/unit/test_worker_digest_job.py` patches `generate_daily_digest`, `_delivery_service`, and `_auto_delivery_recently_sent` inside `apps/worker/src/helm_worker/jobs/digest.py`.
  - `tests/unit/test_digest_delivery_service.py` patches `get_settings` and an async `_send_message` method in `apps/telegram-bot/src/helm_telegram_bot/services/digest_delivery.py`.

This is the dominant seam because many modules instantiate dependencies directly rather than accepting constructor-injected collaborators.

### Contract-oriented repository assertions

- Repository tests validate both behavior and interface conformance with `isinstance(repo, ProtocolType)` checks against runtime-checkable protocols from `packages/storage/src/helm_storage/repositories/contracts.py`.
- `tests/unit/test_storage_repositories.py` is the best reference. It covers ordering, filtering, state transitions, singleton config behavior, and lineage across related records.
- Tests generally assert user-visible outcomes rather than SQL details, which keeps them resilient to internal query refactors.

### API smoke tests

- FastAPI route coverage uses `fastapi.testclient.TestClient`.
- `tests/integration/test_routes.py` checks that the main endpoints respond and that response bodies include expected status markers.
- `tests/unit/test_api_status.py` verifies shape at the service layer without spinning up a client.

These tests are useful guardrails, but they are not enough to prove real workflow correctness across storage, agents, and transport layers together.

## Fixture Style

- The suite currently favors local helper functions and ad hoc fixtures over a large shared `conftest.py`.
- Autouse fixtures are used sparingly. One example is `_default_no_recent_auto_delivery` in `tests/unit/test_worker_digest_job.py`.
- Small inline doubles are common and preferred over mock-heavy scaffolding. Examples include `_DigestResult` in `tests/unit/test_worker_digest_job.py` and `_Settings` in `tests/unit/test_digest_delivery_service.py`.

## Async Testing Pattern

- Async support is enabled globally through `asyncio_mode = "auto"` in `pyproject.toml`.
- Even when production code has async internals, tests often exercise the synchronous wrapper and patch async leaf methods. `tests/unit/test_digest_delivery_service.py` does this by overriding `_send_message` with an async function while still calling `service.deliver(...)` synchronously.
- There is not yet a broad pattern of `pytest.mark.asyncio` tests in the sampled suite.

## What The Existing Tests Prioritize Well

- Hermetic tests with no network calls and no requirement for external Postgres.
- Verification of approval and replay edge cases through status values rather than happy-path-only assertions.
- State transition coverage for repositories and worker control flows.
- Thin API smoke checks to catch route registration regressions.

## Observable Testing Gaps

- End-to-end workflow tests are missing for the main V1 paths: email triage, digest generation plus delivery, study ingest plus task extraction, and approval transitions across bot/API/storage boundaries.
- Integration tests do not currently verify real dependency wiring against the configured app dependencies in `apps/api/src/helm_api/dependencies.py`.
- LLM behavior in `packages/llm/src/helm_llm/client.py` has no direct tests in the current tree.
- Logging behavior and redaction expectations are not explicitly asserted.
- Migration coverage is absent; schema correctness is inferred from ORM tests rather than validated through Alembic upgrade/downgrade flows.

## Practical Guidance For New Tests

- Prefer a focused unit test first when changing a single repository, service, bot command, or worker job.
- Use in-memory SQLite unless the behavior specifically depends on Postgres-only semantics.
- Patch collaborators at the module import seam if the production module constructs them internally.
- When changing API contracts, add one schema-level or service-level test and one route-level test.
- When changing stateful workflow logic, extend `tests/unit/test_storage_repositories.py`-style assertions so transitions and ordering rules stay explicit.
- If you introduce a TODO instead of coverage, match the existing convention and include concrete owner/context in the comment.
