# Database

SQLite is QueueLess's only application database. It stores accounts, branches,
services, counters, queues, queue entries, immutable queue events, notifications,
preferences, and feedback. Every durable resource is written to this database;
transient WebSocket delivery and rate-limit counters remain process-local.
SQLAlchemy ORM statements and bound parameters are used for database access;
user input is never interpolated into SQL.

Set `DATABASE_URL` to a SQLite file URL. Development defaults to
`sqlite:///./queueless.db`; production must use an absolute, persistent file URL
such as `sqlite:////var/data/queueless.db`. The Render blueprint provisions a
50 GB persistent disk and runs migrations against this file before serving
requests. Do not use an in-memory or ephemeral filesystem database for a hosted
service. Monitor free disk space and back up the database file with its SQLite
WAL state handled consistently; use SQLite's backup API or stop the service
before copying files.

Run Alembic from `backend/` to create or update the schema:

```sh
alembic upgrade head
```

The initial migration creates the schema from the SQLAlchemy models. Later
revision identifiers are retained for migration-history continuity; SQLite
creates the current complete model schema in the initial revision. The schema
contract and migration tests verify the model metadata and actual SQLite
database.

SQLite serializes writers. Queue mutations explicitly begin with
`BEGIN IMMEDIATE` so ticket allocation and state transitions read state only
after acquiring the writer lock. Foreign-key enforcement, WAL mode, and a
60-second busy timeout are enabled. Run exactly one backend instance against a
database file; do not share a SQLite file over network storage or scale the
service horizontally. Real-time WebSocket delivery is process-local.

Queue numbers are protected by both the serialized write transaction and a
unique `(queue_id, queue_number)` constraint. Durable notifications and event
records are committed to SQLite.

SQLite supports large database files, but it is not an unlimited or
multi-writer distributed store. The configured 50 GB disk is the deployment's
storage ceiling until it is deliberately resized. The single-writer workload
and local WebSocket delivery make this deployment appropriate for one service
instance, not unbounded horizontal growth. Back up data and plan a database
migration before that capacity or write throughput becomes a limit.
