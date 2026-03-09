# Migrations Runbook

## Generate migration

```bash
bash scripts/new-migration.sh "describe change"
```

## Apply migrations

```bash
bash scripts/migrate.sh
```

For normal local startup via Docker, manual migration is not required because
`docker compose up --build` runs the `migrate` service automatically before API,
worker, and bot services start.

## Notes

- Keep migration files small and reviewable.
- Update `docs/domain/schema-owner.md` when schema contracts change.
