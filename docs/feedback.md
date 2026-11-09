# Feedback and continuous improvement

QueueLess feedback is a persisted workflow, not a client-side survey. The
floating **Feedback** control is available on the public and authenticated
application pages. A submission is confirmed only after the backend stores it
and returns its report reference.

## Submission and privacy

The form records a category, title, description, optional suggestion/rating,
page type, application version, reporter role and authenticated user reference
when applicable, organization/branch references where the server can establish
them, status, priority, and severity. Page context is reduced by replacing
UUID route segments with `:id`; URL query strings and credentials are never
sent.

Queue status pages offer a separate, unchecked-by-default consent option to
share the queue's organization and branch with the reviewers. The backend
verifies that the queue entry belongs to the signed-in customer, derives the
organization and branch, and discards the queue-entry identifier. It does not
record the ticket number, queue position, or estimate in the feedback report.

Authenticated users may select anonymous submission. Anonymous reports are
not linked to the user or organization and cannot appear in the reporter's
history. Queue context cannot be combined with anonymous submission. Security
and privacy submissions are marked high severity/high priority and are visible
to Super Admin reviewers and the authenticated reporter, but not to
organization administrators or other users.

Do not include passwords, authentication tokens, payment information, or
unnecessary personal or queue details in feedback text. The application does
not currently accept file attachments; no attachment endpoint or public file
storage is enabled.

## Review roles and workflow

- Customers, staff, and administrators can list only their own submitted
  reports. They can reply to their reports and, after resolution, indicate
  whether the resolution helped.
- Organization administrators with active membership can review, filter,
  assign, prioritize, reply to, and resolve non-security reports in their own
  organization. Organization scope is enforced by the backend.
- Super Admin can review platform-wide reports, including restricted security
  and privacy reports, and can export the review data. Administrative actions
  such as assignment, status/priority changes, internal notes, task changes,
  and export are written to the audit log.
- Internal notes are stored separately from public replies and are omitted from
  reporter responses.

Allowed report statuses are `new`, `under_review`, `planned`, `in_progress`,
`waiting_for_information`, `resolved`, `declined`, and `duplicate`. The backend
rejects invalid transitions, records status history, and requires a resolution
summary before a report can be marked resolved. A reviewer may record the
version containing a fix; the reporter can then confirm whether it helped.

Authorized reviewers can create a Product Improvement Board task from a
feedback report. Tasks retain their source-report link and move through
`reviewed`, `prioritized`, `assigned`, `implemented`, `tested`, `released`, and
`measured` (or `declined`). An owner is required before assignment, test
evidence before the tested step, a release version before release, and an
outcome note before measurement. Feedback is never executed as code and never
triggers deployment.

## Metrics and exports

The current metrics are computed from persisted reports and expose report
counts by category, status, and reporter role; new/unresolved counts; the
average of supplied ratings; and the share of submitted resolution
confirmations marked helpful. `null` means that no rating/confirmation exists,
not zero. The CSV export is scope-limited and prefixes spreadsheet formula
cells to prevent formula injection.

Report totals are not a standalone quality score. Growth in reports may reflect
more active users or better reporting access as well as increased problems.
Review trends alongside usage and release history.

## Retention and operational limitations

Feedback reports are retained in the application's SQLite database and
administrative actions are auditable. Automated retention expiry, reporter
deletion controls, secure file attachments, e-mail notifications, trend
comparisons before/after releases, SLA-based overdue calculations, duplicate
clustering, and long-term release outcome analytics are not currently
configured. Operators should include feedback data in normal database backup
and access-control procedures and apply the organization's approved retention
policy before production rollout.

The feedback WebSocket uses short-lived, single-use tickets and sends only
report IDs and statuses. A dashboard must use the API to reload details after a
notification or reconnection. Multi-process event fan-out requires the
deployment to provide a shared realtime broker; the current realtime manager,
like the existing queue realtime manager, is process-local.
