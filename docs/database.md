# Database

PostgreSQL is the source of truth for queues and queue entries. The initial
portable schema is in [`database/schema.sql`](../database/schema.sql); future
changes should be represented as Alembic migrations.
