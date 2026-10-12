# Core queue engine

Queue numbers are allocated by locking the queue row in a database transaction,
incrementing `current_number`, and inserting the entry before commit. The
`(queue_id, queue_number)` unique constraint is a second line of protection.
SQLite obtains its writer lock with `BEGIN IMMEDIATE` before checking whether
the customer already has an active entry. The sequence increment, queue entry,
queue event, and join notifications commit or roll back together. A retry by
the same customer returns the existing active ticket rather than allocating a
second number. Realtime notifications are published only after the transaction
commits, so connected clients do not observe an uncommitted ticket.

WebSocket messages are live hints to refresh queue and notification state, not
a durable event stream. Queue events and notifications are persisted in
SQLite, and clients refetch current state after reconnecting. Delivery to live
sockets is process-local, so run one backend instance.

Numbers are monotonically increasing for the lifetime of a queue. They do not
reset automatically at midnight. A new queue must be created when an operator
needs a new numbering cycle; an administrative reset endpoint is intentionally
deferred.

State transitions are deliberately narrow:

```text
WAITING -> CALLED -> SERVING -> COMPLETED
WAITING -> CANCELLED
CALLED  -> SKIPPED
```

Calls and starts can assign a counter. The counter row is locked before checking
for another `CALLED` or `SERVING` entry, preventing two concurrent staff
actions from claiming the same counter. Completing service releases the counter
and automatically calls the oldest waiting customer; skipping a no-show now
does the same. Paused or closed queues do not auto-call another customer.

Estimated wait is calculated as:

```text
waiting people ahead * average service minutes / max(active counters, 1)
```
