# QueueLess

QueueLess is a real-time queue-management application for customers, staff, and
administrators. The customer flow is **JOIN → WAIT → REAL-TIME POSITION →
CALL → SERVE → COMPLETE**. Queue changes and notifications are persisted by
the API; WebSockets deliver live updates, and clients can refetch state after
reconnecting.

## Architecture

- `frontend/` — React, TypeScript, and Vite single-page application.
- `backend/` — FastAPI API, authentication/authorization, SQLAlchemy models,
  queue services, notifications, and WebSockets.
- `backend/alembic/` — SQLite/PostgreSQL database migrations.
- `docs/` — database, deployment, queue, and operations guidance.
- `e2e/` — browser journeys.

The frontend communicates with the backend API; the backend stores every
application resource in its configured database. The frontend never connects
directly to the database. GitHub Pages hosts the static frontend, and the
current Render deployment runs the API with SQLite on a persistent disk at
`/var/data`. Keep one API instance on SQLite because SQLite, WebSocket
delivery, and transient cache state are local to that instance.
Authenticated API requests use revocable bearer sessions rather than
third-party cookies.

The frontend lazy-loads feature pages and optional monitoring, and production
builds split vendor code into cacheable chunks. First-load timing depends on
the browser, network, host startup, and data; see `docs/scaling.md` for
measurement guidance.

## Local development

Requirements: Python 3.12+, Node.js 22+, and npm.

Start the API with its persistent local SQLite file:

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export DATABASE_URL=sqlite:///./queueless.db
export SECRET_KEY="$(openssl rand -hex 32)"
export JWT_SECRET="$(openssl rand -hex 32)"
python -m app.db.init_db
python -m app.cli create-admin
uvicorn app.main:app --reload --port 8000
```

SQLite is the default for local development and the current single-instance
Render deployment. PostgreSQL is also supported by the API for deployments
that need shared, concurrent database access. Configure a managed PostgreSQL
`DATABASE_URL` and the `DATABASE_POOL_*` settings; never commit database
credentials. The SQLite-to-PostgreSQL migration command and its offline,
empty-target requirements are documented in
[docs/database.md](./docs/database.md).

The database file `backend/queueless.db` stores organizations, branches,
organization memberships, services, counters, queues, accounts, sessions,
tickets, events, notifications, preferences, queue requests, and feedback.
Alembic applies schema updates and backfills memberships for existing
organization-assigned staff and administrators.
The one-time admin command prompts for initial credentials and creates the
first administrator. An unassigned first administrator can create the first
organization from Admin → Organizations; that account is then scoped to that
organization. No demo data is loaded at runtime.

For a local customer-flow walkthrough, optionally run
`python -m app.cli seed-demo` from `backend/` while `ENVIRONMENT=development`.
This idempotently creates the clearly labeled QueueLess Demo Center catalog,
branch, published services, and open queues. It refuses to run in other
environments and does not create users, queue tickets, or other activity.

### Bootstrapping the Super Admin

Super Admin access is reserved for one existing, active account whose email
has already been verified through the local account workflow. Set
`SUPER_ADMIN_EMAIL` to that account's exact email in the backend environment,
then run:

```sh
cd backend
python -m app.cli bootstrap-super-admin
```

The command does not create an account or set a password. It refuses missing,
inactive, or unverified accounts, revokes existing sessions on promotion, and
is idempotent for the configured account. Only one Super Admin can exist;
regular Admin APIs cannot grant, change, or deactivate Super Admin access.
After bootstrapping, sign in at `/super-admin/login`. For production, set the
environment variable in the API host's private environment and run the command
in the service shell after database migrations. Never put it in a `VITE_*`
variable or commit it to source control.

Start the frontend in another terminal:

```sh
npm ci --prefix frontend
npm run dev --prefix frontend
```

The local Vite server proxies API and WebSocket requests to
`http://localhost:8000`. The backend accepts either `JWT_SECRET` or
`JWT_SECRET_KEY`; `SECRET_KEY` and the JWT key must be distinct, unique random
values of at least 32 bytes. Never use development secrets in production.
Local password-reset links are printed to the backend console when
`EMAIL_MODE=console`. Production requires an SMTP provider.

PostgreSQL plus Redis are required for multiple API instances: PostgreSQL
provides shared durable state and Redis provides shared WebSocket fan-out,
one-time tickets, and rate limits. This is not a guarantee of 100k+ requests
per second or millions of simultaneously active clients; see
[docs/scaling.md](./docs/scaling.md) before claiming a capacity target.

### Windows PowerShell

From the repository root, initialize the backend with PowerShell commands:

```powershell
Set-Location backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
$env:DATABASE_URL = "sqlite:///./queueless.db"
$env:SECRET_KEY = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
$env:JWT_SECRET = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
python -m app.db.init_db
python -m app.cli create-admin
uvicorn app.main:app --reload --port 8000
```

In a second PowerShell window, from the repository root, start the frontend:

```powershell
npm ci --prefix frontend
npm run dev --prefix frontend
```

## User and admin workflows

Customers sign in at `/login`, join an open service queue, and receive an
estimated position and wait. Staff sign in at `/staff/login`; queue operations
are restricted to their assigned branch. Administrators sign in at
`/admin/login` and manage organizations, branches, services, counters, queues,
users, and analytics. Analytics can be filtered by date range. Administrative
resource changes are recorded in the Super Admin audit log. Admins can download
a date-filtered CSV of queue entries from the analytics dashboard. Administrators
can inspect queue requests and customer ticket details, and mark active tickets
verified. Customers can include an optional service request note when joining,
or submit a free-form queue request for staff to assign to an open queue.

Organization administrators can create staff and additional administrator
accounts from **Admin → Users**. Staff accounts require a branch, and all
accounts created by an organization administrator are assigned to that
administrator's organization. Organization, branch, service, counter, queue,
user, analytics, report, and queue-request APIs enforce organization scope;
records outside the organization are returned as not found or omitted.
Unassigned legacy administrators see no tenant data until a Super Admin
assigns an organization or they create the first organization. Super Admins
retain platform-wide access. Account deactivation revokes active sessions
while retaining queue history and audit records. The API enforces
authentication, roles, organization scope, and staff branch permissions. Staff have dedicated
customer-activity and queue-history views for their assigned branch, alongside
the live queue dashboard.

The **Admin → Migration Center** provides a bounded CSV account import flow.
Download the template and upload a UTF-8 CSV with exactly
`external_id,full_name,email,role,branch_id`; `customer` and `staff` roles are
accepted, and each staff row must identify an active branch in the target
organization. Each preview is tenant-scoped and stored with a SHA-256 file
digest, row-level validation results, and an audit event. An explicit
confirmation is required, and the same unchanged file must be uploaded to
import. Imports create durable source-ID mappings so repeating the same source
IDs skips already imported accounts instead of duplicating them. Existing
email accounts are never linked automatically. Passwords, sessions, and
privileged roles are never imported; new local accounts receive an
unpredictable password hash and must set a password through the password-reset
email flow. Uploads are limited to 2 MiB and 5,000 rows. XLSX, background
processing, branch creation, and rollback are not supported by this CSV
workflow.

The `/super-admin/dashboard` control center is restricted to the bootstrapped
Super Admin role. It links to global user and organization resources, displays
platform counts and application/database health, and provides paginated
security audit logs. Sensitive Super Admin mutations require a session created
within the previous five minutes; sign in again before performing them.

| Role | Main areas |
| --- | --- |
| Customer | Browse services, join queues, track position, history, notifications, profile |
| Staff | Assigned branch dashboard, queue actions, customer activity and history |
| Admin | Organization resources, users, queues, date-filtered analytics |
| Super Admin | Global overview, resource management, role controls, audit log, API/database health |

QueueLess models organizations, branches, services, and queues for settings
such as schools, banks, churches, and temporary events. Administrators set
each service's expected service time. Public service QR codes open the
branch-specific customer join flow.

Core API operations include:

```text
POST /api/v1/queues/{queue_id}/join
POST /api/v1/auth/register
POST /api/v1/admin/organizations/{organization_id}/approve
POST /api/v1/admin/migrations/preview
POST /api/v1/admin/migrations/{job_id}/import
GET  /api/v1/admin/migrations
GET  /api/v1/queues/{queue_id}
GET  /api/v1/queues/{queue_id}/position/{entry_id}
POST /api/v1/queues/{queue_id}/next
POST /api/v1/queue-entries/{entry_id}/call
POST /api/v1/queue-entries/{entry_id}/start
POST /api/v1/queue-entries/{entry_id}/complete
POST /api/v1/queue-entries/{entry_id}/skip
POST /api/v1/queue-entries/{entry_id}/cancel
```

See [docs/queue-engine.md](docs/queue-engine.md) for queue state transitions,
idempotency, and wait-time calculation.

## Authentication, database, and security

The API stores only hashes of opaque session values and accepts session tokens
as bearer credentials. The frontend keeps tokens in tab-scoped
`sessionStorage`, never `localStorage`; logout and password reset revoke the
server-side session. Password-reset tokens are hashed, single-use, and expire
after 30 minutes.

SQLite and PostgreSQL are supported application databases. SQLAlchemy ORM
queries and bound parameters protect database operations from SQL injection.
`backend/.env.example` defaults to `sqlite:///./queueless.db`; production uses
`sqlite:////var/data/queueless.db` on Render's persistent disk. Do not run
multiple API instances against separate local SQLite files. For horizontal scaling, configure PostgreSQL and `REDIS_URL`; Redis provides
shared WebSocket broadcasts, rate limits, and one-time WebSocket tickets.

## Deployment

The staged GitHub Actions workflow builds and deploys the frontend to GitHub
Pages after backend readiness succeeds. Set repository Actions variables
`VITE_API_URL` (HTTPS backend origin), `VITE_WS_URL` (WSS backend origin), and
optionally `VITE_BASE_PATH`. Render mounts a persistent disk at `/var/data`,
uses `/var/data/queueless.db`, and applies Alembic migrations before starting
the API. Configure `CORS_ORIGINS`, `FRONTEND_URL`, `RESET_PASSWORD_URL`, and
the required SMTP values in Render. Never place private values in `VITE_*`
variables.

After deployment, provision the first admin interactively with
`python -m app.cli create-admin` in the service shell. Verify `/ready` returns
HTTP 200 before publishing the frontend. See
[docs/deployment.md](docs/deployment.md), [docs/database.md](docs/database.md),
and [docs/scaling.md](docs/scaling.md) for deployment and persistence details.

## Verification

```sh
cd backend
pytest -q
cd ..
npm run lint --prefix frontend
npm test --prefix frontend
VITE_API_URL=https://api.build.invalid \
VITE_WS_URL=wss://api.build.invalid \
  npm run build --prefix frontend
```

The `.invalid` origins are only for local build validation. Browser test and
deployment checks are described in [TESTING.md](TESTING.md).
