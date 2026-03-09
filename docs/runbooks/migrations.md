# Migrations Runbook

## Generate migration

```bash
bash scripts/new-migration.sh "describe change"
```

## Apply migrations

```bash
bash scripts/migrate.sh
```

## Notes

- Keep migration files small and reviewable.
- Update `docs/domain/schema-owner.md` when schema contracts change.
