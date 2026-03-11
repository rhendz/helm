.PHONY: install format lint test verify smoke doctor bootstrap migrate linear-projects linear-issues linear-export up down

install:
	uv sync --extra dev

bootstrap:
	bash scripts/bootstrap.sh

doctor:
	bash scripts/doctor.sh

lint:
	bash scripts/lint.sh

format:
	bash scripts/format.sh

test:
	bash scripts/test.sh

verify:
	bash scripts/verify.sh

smoke:
	bash scripts/smoke.sh

migrate:
	bash scripts/migrate.sh

linear-projects:
	uv run --frozen --extra dev python scripts/linear_intake.py list-projects

linear-issues:
	uv run --frozen --extra dev python scripts/linear_intake.py list-issues

linear-export:
	uv run --frozen --extra dev python scripts/linear_intake.py export-md --output docs/workstreams/linear-inbox.md

up:
	docker compose up --build

down:
	docker compose down
