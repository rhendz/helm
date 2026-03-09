.PHONY: install lint test smoke doctor bootstrap migrate up down

install:
	python3 -m pip install --upgrade pip
	pip install -e .[dev]

bootstrap:
	bash scripts/bootstrap.sh

doctor:
	bash scripts/doctor.sh

lint:
	bash scripts/lint.sh

test:
	bash scripts/test.sh

smoke:
	bash scripts/smoke.sh

migrate:
	bash scripts/migrate.sh

up:
	docker compose up --build

down:
	docker compose down
