# Database

SQLite is the local-development default. The API also supports PostgreSQL for
deployments requiring concurrent writers and a database shared by multiple
API instances. Both engines persist accounts, organizations, branches,
services, counters, queues, queue entries, queue events, notifications,
preferences, sessions, password-reset tokens, queue requests, and feedback in
the configured database.
The frontend accesses these resources through the authenticated FastAPI API
and never connects directly to the database.

Local development defaults to `sqlite:///./queueless.db`, relative to the
backend working directory. The current Render blueprint still uses
`sqlite:////var/data/queueless.db` on a persistent disk and one API instance.
PostgreSQL connections use `postgresql://` or `postgresql+psycopg://` and the
`DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`, `DATABASE_POOL_TIMEOUT`, and
`DATABASE_POOL_RECYCLE` settings. Supply the connection URL through the host's
secret manager; do not commit credentials. Production must use a persistent
database. Back up SQLite with its online backup API; use the managed or
operator-approved PostgreSQL backup/restore procedure for PostgreSQL.

`DATABASE_BACKUP_DIR` selects a private SQLite backup directory (default
`./backups`). The Super Admin dashboard and CLI SQLite backup tools are
SQLite-specific; PostgreSQL deployments must use managed PostgreSQL backups
or an operator-approved PostgreSQL backup tool.
For file-backed SQLite deployments, the API creates an online backup every
`DATABASE_BACKUP_INTERVAL_HOURS` hours (default `24`; set to `0` to disable)
and applies `DATABASE_BACKUP_RETENTION_COUNT` (default `7`) after each
successful backup. Retention validates snapshots and keeps at least one valid
backup. The schedule is process-local, so keep SQLite to one API process and
monitor application logs and backup storage.

For SQLite, `SQLITE_BUSY_TIMEOUT_MS` (default `30000`) controls how long a
connection waits for a writer, and `SQLITE_SYNCHRONOUS` selects `NORMAL`
(default), `FULL`, or `EXTRA` durability. WAL mode and foreign-key enforcement
are enabled for every connection. SQLite uses the configured database pool
limits, but its single-writer behavior remains; use one API process on local
persistent storage and never share the database file across hosts.

The time engine stores timestamps in UTC and validates IANA timezone names with
Python's `zoneinfo` database. Organizations default to `Africa/Lagos` for new
records; branches retain their explicit timezone override. `GET
/api/v1/time/now` provides an authoritative server timestamp for client clock
offsets, while `GET /api/v1/time/health` reports time-engine health. Durable
scheduled jobs and execution records are stored in `scheduled_jobs` and
`scheduled_job_executions`; pending jobs can be inspected, retried, or
cancelled through the protected scheduler API. The current scheduler
implementation provides durable job state and atomic claiming primitives;
task-specific automation handlers and distributed worker coordination remain
deployment-specific.

Backups are created with SQLite's online backup API, written atomically with
owner-only file permissions, and validated with `PRAGMA integrity_check`.
Scheduled retention only removes older, integrity-checked snapshots beyond the
configured count. Copy verified snapshots to separately secured off-host
storage; a backup on the same disk is not disaster recovery.

SQLite restore is deliberately not an API operation. Stop every QueueLess API
process first, then run:

```sh
cd backend
python -m app.cli database-restore ./backups/<verified-snapshot>.sqlite3 --confirm-offline
alembic upgrade head
```

The CLI rejects restore without the explicit offline confirmation, validates
the snapshot, creates a safety backup of the current database, checkpoints
SQLite WAL, and atomically replaces the database file. Restart the API only
after migrations and integrity checks complete. Validate restores in an
isolated environment and document your deployment's recovery-time and
recovery-point objectives.

Apply schema migrations from `backend/`:

```sh
alembic upgrade head
```

The API deployment runs migrations before serving requests. For local
initialization, run `python -m app.db.init_db`. Migrations are versioned in
`backend/alembic/versions/` and the integration suite runs them against a
disposable SQLite file.

## Migrating SQLite data to PostgreSQL

The migration CLI copies a current, quiesced SQLite database into a fresh
PostgreSQL destination. It does not delete or modify the SQLite source, and it
does not change the deployment's database URL. Use an isolated target first.

1. Take and verify a SQLite backup. Stop every API process and worker using
   the source database and stop writes from other tools.
2. Provision a managed PostgreSQL database with enough disk space for the
   database plus indexes and temporary migration overhead. Keep its URL in
   private environment configuration.
3. Configure the CLI environment with the PostgreSQL `DATABASE_URL`, signing
   keys, and production-required settings. Run from `backend/`; the target
   must be empty or contain only this app's current, empty schema.
4. Run:

   ```sh
   python -m app.cli migrate-sqlite-to-postgresql \
     --source /absolute/path/to/queueless.db \
     --confirm-source-offline
   ```

   The command checks SQLite integrity and migration revisions, applies the
   current Alembic schema to an empty target, copies records in batches inside
   a target transaction, and verifies every table's row count. Use
   `--batch-size` to tune memory use. A failed copy rolls back destination
   records; any schema already created remains empty and can be retried.
5. Review the per-table counts, verify health, authentication, queue flows,
   permissions, and backups against the target. Keep the source and its
   verified backup unchanged until cutover and rollback have been tested.
   Switch the deployment to PostgreSQL only as a separate, deliberate
   operation.

The source must be at the current Alembic head and contain the expected
QueueLess tables. If the CLI finds a different schema, stop and resolve it
before migrating; do not bypass its checks or import into a non-empty target.
This procedure is an offline copy, not zero-downtime replication.

SQLite serializes writers rather than providing PostgreSQL row-level locks.
Keep the current SQLite deployment to one API instance and use its configured
busy timeout and WAL mode. PostgreSQL supports row-level locking and shared
database access, but application-level process-local WebSocket and transient
cache state still prevent safely scaling every application behavior merely by
adding instances.
