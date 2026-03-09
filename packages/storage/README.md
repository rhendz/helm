# package: storage

Purpose: persistence layer (SQLAlchemy models, sessions, repositories, migrations alignment).

Boundaries:

- Own schema evolution and DB contracts.
- Expose simple repository interfaces to app/agent layers.
