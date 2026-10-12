# Runtime limits and operations

QueueLess currently targets a single backend instance with a persistent SQLite
database file. SQLite serializes writes and the queue service acquires the
writer lock before reading or changing queue state. WAL mode permits concurrent
readers, but SQLite remains a single-writer database.

## Supported deployment shape

- One API process and one worker per database file.
- Persistent local storage for SQLite; do not place the file on a network
  filesystem or mount one file into multiple service instances.
- WebSocket broadcasts and short-lived tickets are process-local. Reconnecting
  clients should refetch queue state from the API.
- Notifications and queue events are durable SQLite records. WebSocket
  delivery is an update signal, not the source of truth.

Do not add backend replicas or workers as a performance shortcut. A future
multi-instance design needs a shared transactional database and shared
real-time coordination; it is not achieved by mounting SQLite across nodes.

## Health, backups, and monitoring

- `GET /health` checks process liveness; `GET /ready` checks database
  availability.
- Monitor API latency and errors, SQLite busy/locked errors, disk utilization,
  WebSocket disconnects, and backup completion.
- Use SQLite's online backup API or a service snapshot to back up a live WAL
  database. Verify restoration periodically in an isolated environment.
- Keep Sentry optional and avoid sending credentials, customer details, or
  queue-entry information to monitoring metadata.
- Use client reconnect/backoff and refetch current queue state after
  reconnecting; real-time events are not replayed.

## Load validation

Before production use, run the SQLite-backed test suite including concurrent
queue joins, then exercise expected peak traffic against a disposable copy of
the deployment configuration. Measure writer contention, request latency, disk
growth, restart recovery, and real-time client reconnection. Increase a timeout
or instance size only when measurements identify the bottleneck; capacity and
latency guarantees must be established on the selected hosting plan.
