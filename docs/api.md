# API

All application APIs are served under `/api/v1`.

## Health

`GET /api/health` returns the service status.

## Account settings

`POST /api/v1/auth/register` accepts `requested_role` values `customer`,
`staff`, or `admin` (default `customer`). Customer accounts can sign in
immediately. Staff requests require an active organization and branch and stay
inactive until an organization administrator approves them with
`POST /api/v1/admin/users/{user_id}/approve`. Organization administrator
requests stay inactive until a Super Admin approves them through the same
endpoint. Requests for a new organization require Super Admin approval of the
organization first. Public registration cannot create Super Admin accounts.

Authenticated users can update their display name with
`PATCH /api/v1/auth/me` (`full_name`). The server derives the account and role
from the active session and records the change in the audit log.

`POST /api/v1/auth/change-password` requires `current_password` and a new
`new_password` of 8-128 characters. Changing the password revokes the user's
other active sessions while keeping the verified current session active.
Incorrect current passwords are rejected; passwords and session tokens are
never included in audit records.

## QR join and queue entry

- `GET /api/v1/catalog/services/{service_id}` returns the public service
  information used by a scanned QR code.
- `POST /api/v1/customers/services/{service_id}/join` joins the authenticated
  customer. Branch-specific QR routes pass `branch_id` as a query parameter;
  queue-specific QR routes also pass `queue_id`. The API rejects service,
  branch, or queue mismatches. Generic service links select the least-loaded
  open queue with capacity; an active ticket for that service is reused.
- QR codes contain only the public frontend URL, using
  `/join/{service_id}` or `/join/{branch_id}/{service_id}`, optionally with a
  public `queue_id` query parameter. They never contain credentials, customer
  information, queue-entry IDs, or database details. The join endpoint verifies
  that any selected queue belongs to the service.

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

## Feedback and product improvement

`POST /api/v1/feedback` accepts authenticated or anonymous reports. The
authenticated reporter, role, organization, and branch are derived on the
server; clients cannot assign themselves a role or organization. Repeated
requests carrying the same `idempotency_key` return the same report reference.
Anonymous reports cannot be tracked or answered by the reporter.

Signed-in users can use:

- `GET /api/v1/feedback/mine?page=1&page_size=20` to list their reports.
- `GET /api/v1/feedback/{report_id}` to view a report they submitted or are
  authorized to review.
- `POST /api/v1/feedback/{report_id}/replies` to add a public response.
- `POST /api/v1/feedback/{report_id}/confirm` to report whether a published
  resolution helped.
- `POST` and `DELETE /api/v1/feedback/{report_id}/votes` to vote on a feature
  request.

Organization administrators can use `/feedback/managed`, `/feedback/metrics`,
`/feedback/reviewers`, and `/feedback/export.csv`. Results are limited to the
administrator's active organization membership. Super Admin has platform-wide
access. Security and privacy reports are excluded from organization review and
are visible to Super Admins and their authenticated submitter only. Reviewers
can assign a report, set its priority/severity, add public replies or restricted
internal notes, and change status through validated workflow transitions.
Resolution requires a summary and can record the release version.

Improvement tasks are created from a report with
`POST /api/v1/feedback/{report_id}/tasks`, linked to their source report, and
managed through `/feedback/tasks`. The task workflow records assignment,
acceptance criteria, test evidence, release version, and post-release outcome.

`POST /api/v1/feedback/ws-ticket` issues a short-lived, one-use ticket for
`WS /ws/feedback`. The server sends only report reference/status events and
filters them by reporter, assignee, organization membership, and role. Clients
reload authoritative API state after connect, event, or reconnect.

The shared feedback dialog stores only the current page type and application
version by default. On a queue status page, a signed-in customer may explicitly
opt to share the queue's organization/branch context; the server verifies
ownership and does not persist the queue-entry identifier or ticket details.
File attachments are not currently enabled. Do not send secrets or sensitive
customer details in free text.

## Queue updates

`POST /api/v1/auth/ws-ticket` issues a short-lived, one-use ticket for an
authorized queue subscription. Customers must have an entry in that queue;
staff are limited to their assigned branch; organization administrators need
an active membership and may subscribe only within their organization.
Super Admins may subscribe platform-wide. `WS /ws/queues/{queue_id}` streams
queue updates, while public displays may connect without a ticket and receive
only the public event payload. Clients refetch authoritative API state after
connect, events, and reconnects.

`POST /api/v1/super-admin/ws-ticket` and `WS /ws/super-admin` provide an
authenticated platform-wide stream for the Super Admin dashboard. Queue events
are published after their database transaction commits; the dashboard uses
them to refresh aggregate metrics. Events are process-local and are not
replayed after a disconnect, so clients must reload authoritative state after
reconnecting.

## Appointments and queue policies

Administrators can create future appointment slots with
`POST /api/v1/admin/appointment-slots` using a service ID, timezone-aware
`starts_at`/`ends_at`, and capacity. Organization Admins are constrained to
their active organization's services; Super Admins have platform-wide scope.
`GET /api/v1/admin/appointment-slots?service_id=...` returns the scoped
schedule.

Customers can list open times with
`GET /api/v1/customers/appointment-slots?service_id=...`, book with
`POST /api/v1/customers/appointments`, view their own bookings with
`GET /api/v1/customers/appointments`, and cancel or check in with the
corresponding `POST /{appointment_id}/cancel` and `POST /{appointment_id}/check-in`
routes. Check-in opens 15 minutes before the slot and closes at its end.
Booking capacity is reserved atomically, cancellation releases it, and all
customer reads/actions are owner-scoped. The appointment workflow is distinct
from walk-in queue admission; check-in does not silently create a walk-in
ticket.

Queues may be configured with a nullable `capacity_limit` (unlimited when
null) and `priority_enabled`. Active waiting, called, and serving tickets count
against capacity. When priority is enabled, staff can set waiting-entry levels
0-5 with `POST /api/v1/queue-entries/{entry_id}/priority`; the queue remains
FIFO within each level. Priority changes are audited and published after
commit. Staff can transfer a waiting ticket with
`POST /api/v1/queue-entries/{entry_id}/transfer`; staff are limited to their
assigned branch, organization Admins to their active organization, and Super
Admins have platform-wide access. A transfer creates a new destination ticket,
marks the old ticket cancelled, and records both IDs/numbers for audit/history.

Super Admins can view `GET /api/v1/super-admin/backups` and create an
integrity-checked snapshot with `POST /api/v1/super-admin/backups`. Restore is
kept out of the live API and is performed offline through the backend CLI.

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

## Announcements and platform operations

Authenticated customers and staff can read current audience-matched
announcements at `GET /api/v1/announcements`. The same session can request a
single-use WebSocket ticket at `POST /api/v1/auth/announcements-ws-ticket` and
subscribe to `/ws/announcements`; only announcements intended for that role are
broadcast. Published announcements are persisted in SQLite and expire when
their optional `expires_at` is reached.

Super Admins manage drafts and publication through
`GET|POST /api/v1/super-admin/announcements`,
`PUT /api/v1/super-admin/announcements/{id}`,
`POST /api/v1/super-admin/announcements/{id}/publish`, and
`POST /api/v1/super-admin/announcements/{id}/unpublish`. Write operations
require a recent authenticated Super Admin session and are audited.

`GET /api/v1/super-admin/platform-settings` returns the persisted global
settings. `PUT` updates the maintenance-mode flag and its user-facing message,
requires a recent Super Admin session, and creates an audit event. While
maintenance mode is enabled, regular API requests return HTTP 503; health
checks, login, and Super Admin controls remain available. The current state is
also available at `GET /api/v1/system-status`.

Organization Admins manage staff-only announcements through
`GET|POST /api/v1/admin/announcements`,
`PUT /api/v1/admin/announcements/{id}`,
`POST /api/v1/admin/announcements/{id}/publish`, and
`POST /api/v1/admin/announcements/{id}/unpublish`. Each announcement is
scoped to the Admin's active organization membership and is delivered only to
staff assigned to that organization. Customers cannot receive organization
announcements through this API; customer-facing announcements remain
Super-Admin-controlled global content.
