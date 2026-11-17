# Architecture

QueueLess is a monorepo with a Vite client, FastAPI application layer, SQLite
persistence, process-local WebSocket updates, and a separately versioned AI
wait-time engine. GitHub Pages serves the static frontend, while a single
FastAPI service stores durable application state in a SQLite database on
persistent storage.

The frontend communicates with the API through `/api`, queue streams through
`/ws/queues/{queue_id}`, and the platform-wide Super Admin event stream through
`/ws/super-admin`. Queue WebSocket tickets are checked against customer queue
membership, staff branch assignment, or the administrator's active
organization membership. Only Super Admins may use the platform-wide stream.
Queue state is persisted before these streams publish events. Queue mutations
also append a versioned transactional-outbox record with an idempotency key and
monotonic replay cursor. Reconnecting clients send their last cursor; the
service replays retained events when the cursor is contiguous and sends an
authoritative snapshot when replay is unavailable. Redis pub/sub shares queue,
announcement, and feedback events across API instances when configured; without
Redis, realtime delivery is limited to the connected API process. Production
uses HTTPS, WSS, and revocable
bearer sessions, so cross-origin requests do not depend on third-party
cookies. In local development Vite proxies API and WebSocket paths to the
FastAPI service.

## Time engine

Persistent timestamps are UTC and are produced through
`backend/app/services/time_engine.py`. `GET /api/v1/time/now` returns an
authoritative server timestamp; the frontend renders the intervening seconds
locally and resynchronizes periodically instead of writing heartbeat rows.
Organization and branch time zones are validated against the IANA zoneinfo
database, and local wall-clock inputs reject daylight-saving gaps and
ambiguous times unless an explicit offset is supplied.

Queue estimates use the queue position service and historical service-duration
data, and are always labelled as estimates with a calculation timestamp.
Appointments and scheduled jobs use the same UTC clock. Scheduler jobs are
SQLite-backed with idempotency keys, leases, retry counters, execution
history, and a worker started by the FastAPI lifespan; they therefore survive
application restarts. SQLite WAL, foreign-key enforcement, short transactions,
and the configured busy timeout remain the concurrency boundary.
