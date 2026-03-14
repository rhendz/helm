# Codebase Conventions

## Purpose

This repository favors explicit service code over framework-heavy abstractions. The baseline matches the guidance in `AGENTS.md`: keep modules boring, preserve package boundaries, and store durable state in Postgres-backed models instead of prompt memory.

## Architectural Shape

- App packages orchestrate and expose entrypoints. Examples: `apps/api/src/helm_api/main.py`, `apps/api/src/helm_api/routers/status.py`, `apps/worker/src/helm_worker/jobs/digest.py`, `apps/telegram-bot/src/helm_telegram_bot/services/command_service.py`.
- Package code implements reusable behavior behind those app entrypoints. Examples: `packages/storage/src/helm_storage/repositories/contracts.py`, `packages/storage/src/helm_storage/repositories/action_items.py`, `packages/agents/src/helm_agents/digest_agent.py`, `packages/llm/src/helm_llm/client.py`.
- Storage is treated as the durable source of truth. ORM models in `packages/storage/src/helm_storage/models.py` are extensive and represent real workflow state, while domain-level models in `packages/domain/src/helm_domain/models.py` are intentionally minimal and still marked with TODO follow-up.
- The current code does not introduce a dependency injection container. Instead it uses local factory seams such as `apps/api/src/helm_api/services/email_service.py::_runtime()` and `apps/api/src/helm_api/dependencies.py::get_db()`.

## Python Style

- Python 3.11 is the target in `pyproject.toml`.
- Ruff is the enforced linter via `scripts/lint.sh`, with a 100-character line length and rule sets `E`, `F`, `I`, `UP`, and `B`.
- The codebase uses standard library typing heavily: `list[str]`, `dict[str, str]`, `str | None`, `Generator`, and `Protocol`.
- `from __future__ import annotations` appears where it reduces forward-reference friction, especially in protocol- and service-heavy modules such as `packages/storage/src/helm_storage/repositories/contracts.py` and `apps/telegram-bot/src/helm_telegram_bot/services/command_service.py`.
- Imports are grouped cleanly and left for Ruff/isort to normalize.

## Data Modeling Patterns

- Input contracts are usually immutable dataclasses with `frozen=True, slots=True`. See `packages/storage/src/helm_storage/repositories/contracts.py` for `NewActionItem`, `NewEmailThread`, `NewActionProposal`, and related patch/create payloads.
- Response contracts at the API boundary use Pydantic `BaseModel` classes in `apps/api/src/helm_api/schemas.py`.
- Persistence models use SQLAlchemy 2 typed declarative mappings with `Mapped[...]` and `mapped_column(...)` in `packages/storage/src/helm_storage/models.py`.
- Repository interfaces are defined as runtime-checkable protocols in `packages/storage/src/helm_storage/repositories/contracts.py`, and concrete SQLAlchemy implementations are named `SQLAlchemy...Repository`.

## Service And Module Design

- Keep functions and methods short and single-purpose. `apps/api/src/helm_api/main.py` only assembles routers and exposes `/healthz`; business logic lives elsewhere.
- Prefer thin app-layer functions that translate between transport models and package calls. `apps/api/src/helm_api/routers/status.py` is a good example.
- Repository methods usually perform a single query or state transition and commit immediately inside the method. See `packages/storage/src/helm_storage/repositories/action_items.py`.
- Modules often expose a narrow public surface with `__all__`, as in `apps/api/src/helm_api/services/email_service.py`.
- Constants stay local to the module that owns the behavior, for example `_AUTO_DIGEST_INTERVAL` in `apps/worker/src/helm_worker/jobs/digest.py`.

## Operational Conventions

- Structured logging is the default pattern. `packages/observability/src/helm_observability/logging.py` configures `structlog` JSON output, and callers log event names plus machine-readable fields.
- Logging avoids raw secrets by design, but some jobs still log user-derived previews. `apps/worker/src/helm_worker/jobs/digest.py` logs `digest.text[:120]`, so contributors should keep preview-style logging short and sanitized.
- Potentially meaningful outbound actions keep an explicit approval boundary. The repo reflects that policy through draft approval state in `packages/storage/src/helm_storage/models.py` and Telegram approval flows in `apps/telegram-bot/src/helm_telegram_bot/services/command_service.py`.

## TODO And Comment Discipline

- TODOs include owner or phase context, for example `# TODO(v1-phase2): ...` in `tests/integration/test_scaffold.py` and `packages/llm/src/helm_llm/client.py`.
- Comments are sparse and usually justify a non-obvious gap or future contract, not basic control flow.
- Temporal coordination comments should be avoided unless they are tied to a concrete owner/context and can be removed on the next relevant touch.

## Quality Risks To Preserve Awareness Of

- Some service code still instantiates runtime dependencies directly instead of accepting injected collaborators. This keeps modules simple, but it also makes test seams rely on monkeypatching import-level symbols.
- Repository methods committing internally simplify usage but can make larger transactional workflows harder to compose later.
- `packages/domain/src/helm_domain/models.py` is not yet the center of the system’s domain model; the real behavior currently lives closer to storage, service, and agent packages.

## Practical Guidance For Contributors

- Add new behavior in the package that owns the concern, then keep the app layer as a thin adapter.
- Define new storage payloads and interfaces in `packages/storage/src/helm_storage/repositories/contracts.py` before adding repository implementations.
- Add or update Pydantic schemas in `apps/api/src/helm_api/schemas.py` when API contracts change.
- Keep logging structured and minimal; do not introduce verbose body logging.
- Follow existing naming patterns: `get_*`, `list_*`, `create`, `update`, `mark_completed`, `set_approval_status`, and `run` for worker jobs.
