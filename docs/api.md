# API

All application APIs are served under `/api/v1`.

## Health

`GET /api/health` returns the service status.

## QR join and queue entry

- `GET /api/v1/catalog/services/{service_id}` returns the public service
  information used by a scanned QR code.
- `POST /api/v1/customers/services/{service_id}/join` joins the authenticated
  customer. Branch-specific QR routes pass `branch_id` as a query parameter;
  the API rejects a service/branch mismatch.
- QR codes contain only the public frontend URL, using
  `/join/{service_id}` or `/join/{branch_id}/{service_id}`. They never contain
  credentials, customer information, queue-entry IDs, or database details.
  The service and optional branch identifiers are public catalog identifiers;
  the join endpoint still verifies the service/branch relationship.

## Notifications

The authenticated customer APIs support:

- `GET /api/v1/notifications?page=1&page_size=20` for the notification center.
- `GET /api/v1/notifications/unread-count` for the unread badge/count.
- `POST /api/v1/notifications/{notification_id}/read` and
  `POST /api/v1/notifications/read-all` to update read state.
- `GET` and `PUT /api/v1/notifications/preferences` to retrieve and update
  in-app notification preferences.

Queue entry and status events create durable, idempotent notifications. The
approaching alert threshold is configurable with
`NOTIFICATION_APPROACHING_THRESHOLD` (defaults to 3 people ahead). Browser
notifications are an optional client enhancement; denied permission does not
affect the in-app notification center or queue functionality. SMS is not
required.

## Queue updates

`WS /ws/queues/{queue_id}` streams queue updates. Customer, staff, and public
display clients can reconnect and refresh their queue state through this
stream.

## Wait-time estimation

`GET /api/v1/ai/wait-time/{queue_entry_id}` returns an authenticated customer's
statistical wait estimate for their own queue entry. Staff can request
predictions for entries in their assigned branch. The response includes
`estimated_minutes`, `lower_bound_minutes`, `upper_bound_minutes`, `confidence`,
`model_version`, and the factors used to produce the estimate. This version is
a deterministic statistical model, not a trained machine-learning model or an
external AI service; completed service history is used when available, with a
deterministic fallback when it is not.
The returned `confidence` is a heuristic data-coverage indicator, not a
calibrated probability.
