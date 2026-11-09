# Runtime limits and operations

QueueLess supports SQLite and PostgreSQL. SQLite is appropriate for a single
API instance with moderate write concurrency; it serializes writers. PostgreSQL
provides row-level locks and shared database access, but does not by itself
make the application horizontally scalable.

## Supported deployment shape

- With SQLite, run exactly one API instance against the persistent database
  file.
- PostgreSQL can be shared by multiple API processes when Redis is configured
  for shared realtime state.
- Keep the database on durable storage; container-local filesystems may be
  ephemeral and are not a backup.
- WAL mode and a bounded busy timeout are enabled for concurrent local readers
  and writes when SQLite is used. Queue-number allocation uses an atomic
  database update.
- Authenticated and public queue WebSocket clients reconnect with an event
  cursor; the API replays durable outbox events or sends a current queue
  snapshot, while clients still refetch state after reconnecting.
- Queue connection-attempt protection defaults to 1,000 attempts per queue per
  minute and is configurable with `REALTIME_QUEUE_CONNECTION_LIMIT`; clients
  also refetch every 15 seconds while disconnected or stale.
- Redis shares WebSocket broadcasts, one-time WebSocket tickets, and
  rate-limit counters across API processes. Reconnecting clients still refetch
  durable queue state.

Do not add replicas or workers that use separate SQLite files. PostgreSQL is
the first step for shared concurrent writes, not a promise of a specific
account count, request rate, or latency.

## High-concurrency readiness

The current application has not been load-tested or certified for 5 million
simultaneously active users or 100k+ requests per second. Before scaling,
operate PostgreSQL and Redis as managed shared services, use a load-balanced
stateless API tier, configure database connection pooling (typically via
PgBouncer where appropriate), profile queries and indexes, and run capacity
tests using production-shaped queue, account, and event data. Durable event
delivery, analytics isolation, and retention/partitioning still need
workload-specific design.

Five million stored accounts is a data-volume requirement and is not equivalent
to five million users making requests concurrently. Size and load-test account
lookups, sessions, queue history, and backups against the expected record mix
and traffic. No capacity claim should be made until repeatable tests establish
throughput, latency, recovery, and error-rate targets on the selected host and
database.

## Health, backups, and monitoring

- `GET /health` checks process liveness; `GET /ready` checks database
  availability.
- Back up SQLite with SQLite's online backup mechanism or a quiesced/copy-safe
  procedure; do not assume a live copy of a WAL database includes all
  committed data.
- Use the managed or operator-approved backup procedure for PostgreSQL.
- Verify restore periodically on an isolated instance.
- Keep Sentry optional and avoid sending credentials, customer details, or
  queue-entry information to monitoring metadata.
- Use client reconnect/backoff and refetch current state after reconnecting;
  real-time events are not replayed.

## Load validation

Run the backend suite against its disposable SQLite database, then exercise
expected peak traffic against an isolated deployment using the same instance
size and persistent-disk configuration as production. Measure API latency,
database contention, disk capacity, restart recovery, and realtime
reconnection. Database throughput is workload- and storage-dependent; validate
capacity before increasing traffic.
