# Core queue engine

Queue numbers are allocated by locking the queue row in a database transaction,
incrementing `current_number`, and inserting the entry before commit. The
`(queue_id, queue_number)` unique constraint is a second line of protection.

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
actions from claiming the same counter.

Estimated wait is calculated as:

```text
waiting people ahead * average service minutes / max(active counters, 1)
```
