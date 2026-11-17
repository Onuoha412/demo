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

The deployment target is up to 750 simultaneously active users, not a limit on
the number of stored accounts. The current Render blueprint's single starter
instance and SQLite-compatible configuration are not certified for that
concurrency. Use managed PostgreSQL and Redis, size the API and database
connection pools for the selected plans, and add API instances only after
verifying shared-state behavior and database limits. Do not treat increasing
the instance count alone as evidence of capacity.

`loadtests/queue.js` profile `E` exercises 750 virtual users against a shared
queue using queue-join and queue-read requests. Run it only against an isolated
deployment with disposable data:

```sh
PROFILE=E BASE_URL=https://isolated-api.example \
QUEUE_ID=<isolated-queue-id> LOAD_TEST_PASSWORD=<test-only-password> \
ISOLATED_TEST_TARGET=YES \
k6 run loadtests/queue.js
```

Both scripts create 750 test customers during setup. Set the backend
environment variable `AUTH_RATE_LIMIT_REGISTER=750` only on the isolated test
deployment so registration is not blocked by the normal per-IP limit; restore
the normal limit afterward. The HTTP profile does not test realtime connection
capacity.

`loadtests/websocket.js` opens 750 authenticated queue WebSocket sessions,
keeps them connected for 90 seconds, and triggers a queue join after 30
seconds. It checks connection success, session duration, and whether the queue
update reaches the connected clients. Its default pass criteria require all
750 socket handshakes, at least 99% event delivery, a p95 handshake below five
seconds, and p95 session duration above 85 seconds. Run it separately, using
an isolated queue and disposable database; it creates test accounts and one
queue entry:

```sh
BASE_URL=https://isolated-api.example QUEUE_ID=<isolated-queue-id> \
LOAD_TEST_PASSWORD=<test-only-password> ISOLATED_TEST_TARGET=YES \
k6 run loadtests/websocket.js
```

Both load tests are test procedures, not evidence that the target has passed.
This WebSocket profile has not been run against the selected production-
equivalent host, and it does not certify production readiness. Measure
API/database CPU and memory, connection-pool wait time, database contention,
errors, p95 latency, queue update delivery, and recovery during the test.
Repeat the tests at expected workload levels before claiming the 750-user
realtime target is met.

Capacity depends on the active workload, event rate, queue history, database
and Redis plans, API resources, and host limits. No capacity claim should be
made until repeatable tests establish the required latency, error-rate, and
recovery targets on the selected production-equivalent infrastructure.

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
