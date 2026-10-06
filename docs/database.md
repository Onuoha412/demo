# Database

PostgreSQL is the source of truth for organizations, branches, services,
counters, queues, queue entries, immutable queue events, notifications, and
feedback. The canonical SQL schema is in
[`database/schema.sql`](../database/schema.sql); the matching initial Alembic
revision is in `backend/alembic/versions/0001_initial_schema.py`.

Queue entries use a per-queue unique position, queue events preserve lifecycle
history, and feedback is limited to one submission per customer and entry.

The database is created only through Alembic. Docker starts PostgreSQL but does
not mount schema files into the container. Run `alembic upgrade head` from
`backend/` against an empty database, then optionally load
`database/seeds/demo_data.sql`.
